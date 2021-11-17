import random

from .random import Random
from .sticky_artist import StickyArtist
from .recommender import Recommender

class NewRecommender(Recommender):
    """
    Recommend personalized tracks for each user cached in Redis.
    Fall back to the random recommender if no recommendations found for the user.
    """

    def __init__(self, user_recommendations, tracks_redis, artists_redis, catalog):
        self.catalog = catalog
        self.user_recommendations = user_recommendations
        self.tracks_redis = tracks_redis
        self.artists_redis = artists_redis
        self.fallback = Random(tracks_redis)
        self.fallback_sticky = StickyArtist(tracks_redis, artists_redis, catalog)


    def recommend_next(self, user: int, prev_track: int, prev_track_time: float) -> int:
        recs = self.user_recommendations.get(user)
        if recs is not None:
            recs = self.catalog.from_bytes(recs)
        else:
            return self.fallback_sticky.recommend_next(user, prev_track, prev_track_time)

        if len(recs) > 0:
            index = random.randint(0, len(recs) - 1)
            if recs[index] == prev_track:
                return self.fallback_sticky.recommend_next(user, prev_track, prev_track_time)
            else:
                return recs[index]
        else:
            return self.fallback_sticky.recommend_next(user, prev_track, prev_track_time)