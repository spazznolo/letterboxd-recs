# Recommender

## Social-only model (v1)
This model recommends films based on followee activity, weighted by how similar each followee is to you.

### Core formula
For each followee `u` and film `f`:

```
score(f) += followee_weight(u)
            * similarity(u)
            * interaction_weight(u,f)
            * time_weight(f)
```

### Followee weight
Penalizes extremely heavy watchers:

```
followee_weight(u) = 1 / sqrt(watched_count(u))
```

### Similarity (overlap + rating alignment)
We compute similarity from two signals:

1) **Watched overlap (Jaccard)**
```
J = |Watched_me ∩ Watched_u| / |Watched_me ∪ Watched_u|
```

2) **Rating alignment with Bayesian shrinkage**
For overlapping rated films, compute avg diff and convert to agreement:

```
agreement = 1 - (avg_diff / 5.0)
```

Then shrink toward a prior (defaults to 0.5):

```
A = (n * agreement + k * prior) / (n + k)
```

Final similarity:

```
similarity(u) = jaccard_weight * J + rating_weight * A
```

### Interaction weight
Piecewise rating score:

- ratings <= 2.5 map to a negative range
- ratings >= 3.0 map to a positive range
- no rating on watched → `unrated`
- watchlist-only → `unrated * watchlist_multiplier`

### Time weight
Linear decay by release year:

- films `time_weight_years` years old → `time_weight_min`
- current year → 1.0
- unknown year → 0.75 (configurable in code)

## Config
All weights live in `config.toml`:

```toml
[social]
watched_weight = 1.0
watchlist_weight = 0.5
time_weight_min = 0.25
time_weight_years = 25

[social_similarity]
jaccard_weight = 0.6
rating_weight = 0.4
rating_prior = 0.5
rating_k = 10
default_similarity = 0.5

[social_ratings]
negative_min = -1.0
negative_max = -0.1
positive_min = 0.1
positive_max = 1.0
unrated = 0.25
watchlist_multiplier = 0.5
```

## CLI
Recommend:
```bash
letterboxd-recs recommend USERNAME --limit 50
```

Inspect similarity breakdown:
```bash
letterboxd-recs similarities USERNAME --limit 30
```

## Notes / Future improvements
- Add diversity penalties
- Add watchlist-only exclusion option
- Blend with content-based model
- Include review text or tags
