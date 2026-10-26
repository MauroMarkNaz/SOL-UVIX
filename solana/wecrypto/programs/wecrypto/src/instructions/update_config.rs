use anchor_lang::prelude::*;
use crate::constants::*;
use crate::error::WeCryptoError;
use crate::state::GlobalConfig;

#[derive(Accounts)]
pub struct UpdateConfig<'info> {
    #[account(
        mut,
        seeds = [GLOBAL_CONFIG_SEED],
        bump = config.bump,
        has_one = authority @ WeCryptoError::Unauthorized
    )]
    pub config: Account<'info, GlobalConfig>,
    pub authority: Signer<'info>,
}

pub fn handle_update_config(
    ctx: Context<UpdateConfig>,
    new_authority: Option<Pubkey>,
    new_idl_uri: Option<String>,
    paused: Option<bool>,
) -> Result<()> {
    let config = &mut ctx.accounts.config;

    if let Some(auth) = new_authority {
        config.authority = auth;
    }
    if let Some(uri) = new_idl_uri {
        require!(uri.len() <= 128, WeCryptoError::IdlUriTooLong);
        config.idl_uri = uri;
    }
    if let Some(p) = paused {
        config.paused = p;
    }

    msg!("WeCrypto config updated. IDL URI: {}, Paused: {}", config.idl_uri, config.paused);
    Ok(())
}
