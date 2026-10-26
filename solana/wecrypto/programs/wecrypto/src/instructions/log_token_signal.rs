use anchor_lang::prelude::*;
use crate::constants::*;
use crate::error::WeCryptoError;
use crate::state::{GlobalConfig, TokenSignalRecord};

#[derive(Accounts)]
#[instruction(
    token_mint: Pubkey,
    risk_verdict: u8,
    risk_score_bps: u16,
    bundle_cluster_detected: bool,
    lp_burned_or_locked: bool,
    details_hash: [u8; 32]
)]
pub struct LogTokenSignal<'info> {
    #[account(
        mut,
        seeds = [GLOBAL_CONFIG_SEED],
        bump = config.bump,
        has_one = authority @ WeCryptoError::Unauthorized
    )]
    pub config: Account<'info, GlobalConfig>,
    #[account(
        init_if_needed,
        payer = payer,
        space = 8 + TokenSignalRecord::INIT_SPACE,
        seeds = [TOKEN_SIGNAL_SEED, token_mint.as_ref()],
        bump
    )]
    pub signal_record: Account<'info, TokenSignalRecord>,
    #[account(mut)]
    pub payer: Signer<'info>,
    pub authority: Signer<'info>,
    pub system_program: Program<'info, System>,
}

pub fn handle_log_token_signal(
    ctx: Context<LogTokenSignal>,
    token_mint: Pubkey,
    risk_verdict: u8,
    risk_score_bps: u16,
    bundle_cluster_detected: bool,
    lp_burned_or_locked: bool,
    details_hash: [u8; 32],
) -> Result<()> {
    let config = &mut ctx.accounts.config;
    require!(!config.paused, WeCryptoError::ProgramPaused);

    let record = &mut ctx.accounts.signal_record;
    record.token_mint = token_mint;
    record.risk_verdict = risk_verdict;
    record.risk_score_bps = risk_score_bps;
    record.bundle_cluster_detected = bundle_cluster_detected;
    record.lp_burned_or_locked = lp_burned_or_locked;
    record.details_hash = details_hash;
    record.eval_timestamp = Clock::get()?.unix_timestamp;
    record.updated_at_slot = Clock::get()?.slot;
    record.bump = ctx.bumps.signal_record;

    config.total_signals += 1;

    msg!("Logged token signal for {} risk: {} bps", token_mint, risk_score_bps);
    Ok(())
}
