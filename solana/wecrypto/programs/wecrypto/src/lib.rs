pub mod constants;
pub mod error;
pub mod instructions;
pub mod state;

use anchor_lang::prelude::*;

pub use constants::*;
pub use instructions::*;
pub use state::*;

declare_id!("9HLcTyxqXTimBXj9RvP2dZtTwZsNdzdiGRNRdUTTUp5B");

#[program]
pub mod wecrypto {
    use super::*;

    pub fn initialize(ctx: Context<Initialize>, idl_uri: Option<String>) -> Result<()> {
        handle_initialize(ctx, idl_uri)
    }

    pub fn update_config(
        ctx: Context<UpdateConfig>,
        new_authority: Option<Pubkey>,
        new_idl_uri: Option<String>,
        paused: Option<bool>,
    ) -> Result<()> {
        handle_update_config(ctx, new_authority, new_idl_uri, paused)
    }

    pub fn record_turn_proof(
        ctx: Context<RecordTurnProof>,
        sequence: u64,
        turn_hash: [u8; 32],
        prev_hash: [u8; 32],
        timestamp: i64,
        emitter_id: String,
        d1_source_id: String,
    ) -> Result<()> {
        handle_record_turn_proof(
            ctx,
            sequence,
            turn_hash,
            prev_hash,
            timestamp,
            emitter_id,
            d1_source_id,
        )
    }

    pub fn commit_prediction(
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
        handle_commit_prediction(
            ctx,
            market_id,
            sequence,
            market_type,
            regime,
            strike_or_band,
            touch_prob_bps,
            settle_prob_bps,
            expiry_at,
            spot_at_commit,
        )
    }

    pub fn resolve_prediction(
        ctx: Context<ResolvePrediction>,
        realized_outcome: u8,
        settlement_price: u64,
        brier_score_e4: u32,
    ) -> Result<()> {
        handle_resolve_prediction(
            ctx,
            realized_outcome,
            settlement_price,
            brier_score_e4,
        )
    }

    pub fn log_token_signal(
        ctx: Context<LogTokenSignal>,
        token_mint: Pubkey,
        risk_verdict: u8,
        risk_score_bps: u16,
        bundle_cluster_detected: bool,
        lp_burned_or_locked: bool,
        details_hash: [u8; 32],
    ) -> Result<()> {
        handle_log_token_signal(
            ctx,
            token_mint,
            risk_verdict,
            risk_score_bps,
            bundle_cluster_detected,
            lp_burned_or_locked,
            details_hash,
        )
    }
}
