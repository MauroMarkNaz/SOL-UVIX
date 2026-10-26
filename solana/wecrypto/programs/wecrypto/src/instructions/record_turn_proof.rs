use anchor_lang::prelude::*;
use crate::constants::*;
use crate::error::WeCryptoError;
use crate::state::{GlobalConfig, PoHTurnAnchor};

#[derive(Accounts)]
#[instruction(
    sequence: u64,
    turn_hash: [u8; 32],
    prev_hash: [u8; 32],
    timestamp: i64,
    emitter_id: String,
    d1_source_id: String
)]
pub struct RecordTurnProof<'info> {
    #[account(
        mut,
        seeds = [GLOBAL_CONFIG_SEED],
        bump = config.bump,
        has_one = authority @ WeCryptoError::Unauthorized
    )]
    pub config: Account<'info, GlobalConfig>,
    #[account(
        init,
        payer = payer,
        space = 8 + PoHTurnAnchor::INIT_SPACE,
        seeds = [POH_TURN_SEED, &sequence.to_le_bytes()],
        bump
    )]
    pub turn_anchor: Account<'info, PoHTurnAnchor>,
    #[account(mut)]
    pub payer: Signer<'info>,
    pub authority: Signer<'info>,
    pub system_program: Program<'info, System>,
}

pub fn handle_record_turn_proof(
    ctx: Context<RecordTurnProof>,
    sequence: u64,
    turn_hash: [u8; 32],
    prev_hash: [u8; 32],
    timestamp: i64,
    emitter_id: String,
    d1_source_id: String,
) -> Result<()> {
    let config = &mut ctx.accounts.config;
    require!(!config.paused, WeCryptoError::ProgramPaused);
    require!(sequence == config.total_turn_anchors + 1, WeCryptoError::InvalidSequence);
    require!(emitter_id.len() <= 64, WeCryptoError::EmitterTooLong);
    require!(d1_source_id.len() <= 64, WeCryptoError::D1SourceIdTooLong);

    let anchor = &mut ctx.accounts.turn_anchor;
    anchor.sequence = sequence;
    anchor.turn_hash = turn_hash;
    anchor.prev_hash = prev_hash;
    anchor.timestamp = timestamp;
    anchor.emitter_id = emitter_id;
    anchor.d1_source_id = d1_source_id;
    anchor.recorded_at_slot = Clock::get()?.slot;
    anchor.bump = ctx.bumps.turn_anchor;

    config.total_turn_anchors = sequence;

    msg!("Recorded UVIX PoH Turn Anchor #{} hash: {:?}", sequence, turn_hash);
    Ok(())
}
