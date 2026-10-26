use anchor_lang::prelude::*;

#[account]
#[derive(InitSpace)]
pub struct GlobalConfig {
    pub authority: Pubkey,
    #[max_len(128)]
    pub idl_uri: String,
    pub paused: bool,
    pub total_turn_anchors: u64,
    pub total_predictions: u64,
    pub total_signals: u64,
    pub bump: u8,
}

#[account]
#[derive(InitSpace)]
pub struct PoHTurnAnchor {
    pub sequence: u64,
    pub turn_hash: [u8; 32],
    pub prev_hash: [u8; 32],
    pub timestamp: i64,
    #[max_len(64)]
    pub emitter_id: String,
    #[max_len(64)]
    pub d1_source_id: String,
    pub recorded_at_slot: u64,
    pub bump: u8,
}

#[account]
#[derive(InitSpace)]
pub struct PredictionCommitment {
    pub sequence: u64,
    #[max_len(64)]
    pub market_id: String,
    pub market_type: u8, // 0: Touch, 1: Settlement, 2: Hourly Ladder Band
    #[max_len(32)]
    pub regime: String, // e.g. "horizon_fp_sv"
    pub strike_or_band: i64,
    pub touch_prob_bps: u16,
    pub settle_prob_bps: u16,
    pub committed_at: i64,
    pub expiry_at: i64,
    pub spot_at_commit: u64,
    pub resolved: bool,
    pub realized_outcome: u8, // 0: Pending, 1: Hit/Yes, 2: Miss/No
    pub settlement_price: u64,
    pub brier_score_e4: u32,
    pub resolved_at: i64,
    pub bump: u8,
}

#[account]
#[derive(InitSpace)]
pub struct TokenSignalRecord {
    pub token_mint: Pubkey,
    pub risk_verdict: u8, // 0: Low, 1: Medium, 2: High
    pub risk_score_bps: u16,
    pub bundle_cluster_detected: bool,
    pub lp_burned_or_locked: bool,
    pub details_hash: [u8; 32],
    pub eval_timestamp: i64,
    pub updated_at_slot: u64,
    pub bump: u8,
}
