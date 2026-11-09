// Pure JS BLAKE3 implementation (RFC / official spec compliant)
const IV = new Uint32Array([
  0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
  0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19,
]);

const MSG_PERMUTATION = [2, 6, 3, 10, 7, 0, 4, 13, 1, 11, 12, 5, 9, 14, 15, 8];

const CHUNK_START = 1;
const CHUNK_END = 2;
const PARENT = 4;
const ROOT = 8;

function rotr(w, r) {
  return (w >>> r) | (w << (32 - r));
}

function g(state, a, b, c, d, mx, my) {
  state[a] = (state[a] + state[b] + mx) | 0;
  state[d] = rotr(state[d] ^ state[a], 16);
  state[c] = (state[c] + state[d]) | 0;
  state[b] = rotr(state[b] ^ state[c], 12);
  state[a] = (state[a] + state[b] + my) | 0;
  state[d] = rotr(state[d] ^ state[a], 8);
  state[c] = (state[c] + state[d]) | 0;
  state[b] = rotr(state[b] ^ state[c], 7);
}

function round(state, m) {
  // Columns
  g(state, 0, 4, 8, 12, m[0], m[1]);
  g(state, 1, 5, 9, 13, m[2], m[3]);
  g(state, 2, 6, 10, 14, m[4], m[5]);
  g(state, 3, 7, 11, 15, m[6], m[7]);
  // Diagonals
  g(state, 0, 5, 10, 15, m[8], m[9]);
  g(state, 1, 6, 11, 12, m[10], m[11]);
  g(state, 2, 7, 8, 13, m[12], m[13]);
  g(state, 3, 4, 9, 14, m[14], m[15]);
}

function compress(cv, block, blockLen, counter, flags) {
  const state = new Uint32Array(16);
  state.set(cv, 0);
  state.set(IV, 8);
  state[12] = counter & 0xffffffff;
  state[13] = (counter / 0x100000000) & 0xffffffff;
  state[14] = blockLen;
  state[15] = flags;

  let m = new Uint32Array(16);
  const view = new DataView(block.buffer, block.byteOffset, block.byteLength);
  for (let i = 0; i < 16; i++) {
    m[i] = i * 4 < blockLen ? view.getUint32(i * 4, true) : 0;
  }

  for (let r = 0; r < 7; r++) {
    round(state, m);
    const nextM = new Uint32Array(16);
    for (let i = 0; i < 16; i++) nextM[i] = m[MSG_PERMUTATION[i]];
    m = nextM;
  }

  const out = new Uint32Array(8);
  for (let i = 0; i < 8; i++) {
    out[i] = state[i] ^ state[i + 8];
  }
  return out;
}

export function blake3(input) {
  let bytes;
  if (typeof input === "string") {
    bytes = new TextEncoder().encode(input);
  } else if (input instanceof Uint8Array) {
    bytes = input;
  } else {
    bytes = new Uint8Array(input);
  }

  // Handle empty input
  if (bytes.length === 0) {
    const emptyBlock = new Uint8Array(64);
    const cvWords = compress(IV, emptyBlock, 0, 0, CHUNK_START | CHUNK_END | ROOT);
    const out = new Uint8Array(32);
    new DataView(out.buffer).setUint32(0, cvWords[0], true);
    for (let i = 0; i < 8; i++) {
      new DataView(out.buffer).setUint32(i * 4, cvWords[i], true);
    }
    return out;
  }

  // Chunks
  const CHUNK_LEN = 1024;
  const chunkCount = Math.ceil(bytes.length / CHUNK_LEN) || 1;

  function hashChunk(chunkBytes, chunkCounter, isRoot) {
    let cv = IV;
    const blockCount = Math.ceil(chunkBytes.length / 64) || 1;
    for (let b = 0; b < blockCount; b++) {
      const start = b * 64;
      const end = Math.min(start + 64, chunkBytes.length);
      const block = new Uint8Array(64);
      block.set(chunkBytes.subarray(start, end));
      const blockLen = end - start;
      let flags = 0;
      if (b === 0) flags |= CHUNK_START;
      if (b === blockCount - 1) flags |= CHUNK_END;
      if (isRoot && b === blockCount - 1) flags |= ROOT;
      cv = compress(cv, block, blockLen, chunkCounter, flags);
    }
    const out = new Uint8Array(32);
    const view = new DataView(out.buffer);
    for (let i = 0; i < 8; i++) view.setUint32(i * 4, cv[i], true);
    return out;
  }

  if (chunkCount === 1) {
    return hashChunk(bytes, 0, true);
  }

  // Multiple chunks: build Merkle tree of chunks
  let cvs = [];
  for (let c = 0; c < chunkCount; c++) {
    const chunkBytes = bytes.subarray(c * CHUNK_LEN, Math.min((c + 1) * CHUNK_LEN, bytes.length));
    cvs.push(hashChunk(chunkBytes, c, false));
  }

  function wordsFromBytes(b32) {
    const w = new Uint32Array(8);
    const dv = new DataView(b32.buffer, b32.byteOffset, 32);
    for (let i = 0; i < 8; i++) w[i] = dv.getUint32(i * 4, true);
    return w;
  }

  while (cvs.length > 1) {
    const nextCvs = [];
    for (let i = 0; i < cvs.length; i += 2) {
      if (i + 1 < cvs.length) {
        const isRoot = (cvs.length === 2);
        const block = new Uint8Array(64);
        block.set(cvs[i], 0);
        block.set(cvs[i + 1], 32);
        const cvWords = compress(IV, block, 64, 0, PARENT | (isRoot ? ROOT : 0));
        const out = new Uint8Array(32);
        const view = new DataView(out.buffer);
        for (let j = 0; j < 8; j++) view.setUint32(j * 4, cvWords[j], true);
        nextCvs.push(out);
      } else {
        nextCvs.push(cvs[i]);
      }
    }
    cvs = nextCvs;
  }

  return cvs[0];
}

export function blake3Hex(input) {
  const bytes = blake3(input);
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}
