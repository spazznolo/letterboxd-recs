# Tuning

## Graph depth + decay
- Increase depth for broader reach, but use lower decay to avoid noise.

## Interaction weights
- liked > rated > watched > watchlist
- Adjust in config.toml for experimentation.

## Blend weights
- Start with content-heavy (alpha ~0.6) and social ~0.3.
- Use novelty to surface under-seen candidates.
