use anchor_lang::prelude::*;
use crate::constants::*;
use crate::error::WeCryptoError;
use crate::state::{GlobalConfig, PredictionCommitment};

#[derive(Accounts)]
#[instruction(
    market_id: String,
    sequence: u64,
    market_type: u8,
    regime: String,
    strike_or_band: i64,
    touch_prob_bps: u16,
    settle_prob_bps: u16,
    expiry_at: i64,
    spot_at_commit: u64
)]
pub struct CommitPrediction<'info> {
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
        space = 8 + PredictionCommitment::INIT_SPACE,
        seeds = [PREDICTION_SEED, market_id.as_bytes(), &sequence.to_le_bytes()],
        bump
    )]
    pub prediction: Account<'info, PredictionCommitment>,
    #[account(mut)]
    pub payer: Signer<'info>,
    pub authority: Signer<'info>,
    pub system_program: Program<'info, System>,
}

pub fn handle_commit_prediction(
    ctx: Context<CommitPrediction>,
    market_id: String,
    sequence: u64,
    market_type: u8,
    regime: String,
    strike_or_band: i64,
    touch_prob_bps: u16,
    settle_prob_bps: u16,
    expiry_at: i64,
    spot_at_commit: u64,
) -> Result<()> {
    let config = &mut ctx.accounts.config;
    require!(!config.paused, WeCryptoError::ProgramPaused);
    require!(market_id.len() <= 64, WeCryptoError::MarketIdTooLong);
    require!(regime.len() <= 32, WeCryptoError::RegimeTooLong);
    require!(touch_prob_bps <= 10000, WeCryptoError::InvalidProbability);
    require!(settle_prob_bps <= 10000, WeCryptoError::InvalidProbability);

    let pred = &mut ctx.accounts.prediction;
    pred.sequence = sequence;
    pred.market_id = market_id;
    pred.market_type = market_type;
    pred.regime = regime;
    pred.strike_or_band = strike_or_band;
    pred.touch_prob_bps = touch_prob_bps;
    pred.settle_prob_bps = settle_prob_bps;
    pred.committed_at = Clock::get()?.unix_timestamp;
    pred.expiry_at = expiry_at;
    pred.spot_at_commit = spot_at_commit;
    pred.resolved = false;
    pred.realized_outcome = 0;
    pred.settlement_price = 0;
    pred.brier_score_e4 = 0;
    pred.resolved_at = 0;
    pred.bump = ctx.bumps.prediction;

    config.total_predictions += 1;

    msg!("Committed prediction for {} seq: {}", pred.market_id, sequence);
    Ok(())
}
