use anchor_lang::prelude::*;
use crate::constants::*;
use crate::error::WeCryptoError;
use crate::state::{GlobalConfig, PredictionCommitment};

#[derive(Accounts)]
pub struct ResolvePrediction<'info> {
    #[account(
        seeds = [GLOBAL_CONFIG_SEED],
        bump = config.bump,
        has_one = authority @ WeCryptoError::Unauthorized
    )]
    pub config: Account<'info, GlobalConfig>,
    #[account(
        mut,
        seeds = [PREDICTION_SEED, prediction.market_id.as_bytes(), &prediction.sequence.to_le_bytes()],
        bump = prediction.bump
    )]
    pub prediction: Account<'info, PredictionCommitment>,
    pub authority: Signer<'info>,
}

pub fn handle_resolve_prediction(
    ctx: Context<ResolvePrediction>,
    realized_outcome: u8,
    settlement_price: u64,
    brier_score_e4: u32,
) -> Result<()> {
    let pred = &mut ctx.accounts.prediction;
    require!(!pred.resolved, WeCryptoError::PredictionAlreadyResolved);

    pred.resolved = true;
    pred.realized_outcome = realized_outcome;
    pred.settlement_price = settlement_price;
    pred.brier_score_e4 = brier_score_e4;
    pred.resolved_at = Clock::get()?.unix_timestamp;

    msg!("Resolved prediction {} seq: {} outcome: {}", pred.market_id, pred.sequence, realized_outcome);
    Ok(())
}
