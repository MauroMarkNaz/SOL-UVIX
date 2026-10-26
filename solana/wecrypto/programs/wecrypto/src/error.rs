use anchor_lang::prelude::*;

#[error_code]
pub enum WeCryptoError {
    #[msg("Program is currently paused")]
    ProgramPaused,
    #[msg("Unauthorized: Signer is not the program authority")]
    Unauthorized,
    #[msg("Invalid PoH sequence: must be strictly monotonic")]
    InvalidSequence,
    #[msg("Invalid previous hash chaining for PoH proof")]
    InvalidPrevHash,
    #[msg("Prediction already resolved")]
    PredictionAlreadyResolved,
    #[msg("Invalid probability basis points: must be <= 10000")]
    InvalidProbability,
    #[msg("Market ID exceeds maximum length (64 chars)")]
    MarketIdTooLong,
    #[msg("Regime identifier exceeds maximum length (32 chars)")]
    RegimeTooLong,
    #[msg("Emitter identifier exceeds maximum length (64 chars)")]
    EmitterTooLong,
    #[msg("D1 source identifier exceeds maximum length (64 chars)")]
    D1SourceIdTooLong,
    #[msg("IDL URI exceeds maximum length (128 chars)")]
    IdlUriTooLong,
}
