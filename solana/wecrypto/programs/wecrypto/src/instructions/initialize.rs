use anchor_lang::prelude::*;
use crate::constants::*;
use crate::error::WeCryptoError;
use crate::state::GlobalConfig;

#[derive(Accounts)]
pub struct Initialize<'info> {
    #[account(
        init,
        payer = payer,
        space = 8 + GlobalConfig::INIT_SPACE,
        seeds = [GLOBAL_CONFIG_SEED],
        bump
    )]
    pub config: Account<'info, GlobalConfig>,
    #[account(mut)]
    pub payer: Signer<'info>,
    pub system_program: Program<'info, System>,
}

pub fn handle_initialize(ctx: Context<Initialize>, idl_uri: Option<String>) -> Result<()> {
    let config = &mut ctx.accounts.config;
    let uri = idl_uri.unwrap_or_else(|| DEFAULT_IDL_URI.to_string());
    require!(uri.len() <= 128, WeCryptoError::IdlUriTooLong);

    config.authority = ctx.accounts.payer.key();
    config.idl_uri = uri;
    config.paused = false;
    config.total_turn_anchors = 0;
    config.total_predictions = 0;
    config.total_signals = 0;
    config.bump = ctx.bumps.config;

    msg!("WeCrypto initialized with IDL endpoint: {}", config.idl_uri);
    Ok(())
}
