import json
import logging
import time
from dataclasses import asdict
from datetime import datetime

from flask import Flask
from flask_redis import Redis
from flask_restful import Resource, Api, abort, reqparse

from botify.data import DataLogger, Datum
from botify.experiment import Experiments, Treatment
from botify.recommenders.newrecommender import NewRecommender
from botify.recommenders.random import Random
from botify.recommenders.sticky_artist import StickyArtist
from botify.recommenders.toppop import TopPop
from botify.recommenders.contextual import Contextual
from botify.track import Catalog

root = logging.getLogger()
root.setLevel("INFO")

app = Flask(__name__)
app.config.from_file("config.json", load=json.load)
api = Api(app)
tracks_redis = Redis(app)
artists_redis = Redis(app, config_prefix="REDIS_ARTISTS")
user_recommendations = Redis(app, config_prefix="USER_RECOMMENDATIONS")
data_logger = DataLogger(app)

catalog = Catalog(app).load(
    app.config["TRACKS_CATALOG"], app.config["TOP_TRACKS_CATALOG"], app.config["USER_RECOMMENDATIONS_FILE_PATH"]
)
catalog.upload_tracks(tracks_redis.connection)
catalog.upload_artists(artists_redis.connection)
catalog.upload_new_user_recommendations(user_recommendations.connection)

parser = reqparse.RequestParser()
parser.add_argument("track", type=int, location="json", required=True)
parser.add_argument("time", type=float, location="json", required=True)


class Hello(Resource):
    def get(self):
        return {
            "status": "alive",
            "message": "welcome to botify, the best toy music recommender",
        }


class Track(Resource):
    def get(self, track: int):
        data = tracks_redis.connection.get(track)
        if data is not None:
            return asdict(catalog.from_bytes(data))
        else:
            abort(404, description="Track not found")


class NextTrack(Resource):
    def post(self, user: int):
        start = time.time()

        args = parser.parse_args()

        treatment = Experiments.AB.assign(user)
        if treatment == Treatment.T1:
            recommender = NewRecommender(user_recommendations.connection, tracks_redis.connection,
                                         artists_redis.connection, catalog)
        elif treatment == Treatment.T2:
            recommender = StickyArtist(tracks_redis.connection, artists_redis.connection, catalog)

        elif treatment == Treatment.T3:
            recommender = Contextual(tracks_redis.connection, catalog)

        else:
            recommender = Random(tracks_redis.connection)

        recommendation = recommender.recommend_next(user, args.track, args.time)

        data_logger.log(
            "next",
            Datum(
                int(datetime.now().timestamp() * 1000),
                user,
                args.track,
                args.time,
                time.time() - start,
                recommendation,
            ),
        )
        return {"user": user, "track": recommendation}


class LastTrack(Resource):
    def post(self, user: int):
        start = time.time()
        args = parser.parse_args()
        data_logger.log(
            "last",
            Datum(
                int(datetime.now().timestamp() * 1000),
                user,
                args.track,
                args.time,
                time.time() - start,
            ),
        )
        return {"user": user}


api.add_resource(Hello, "/")
api.add_resource(Track, "/track/<int:track>")
api.add_resource(NextTrack, "/next/<int:user>")
api.add_resource(LastTrack, "/last/<int:user>")


if __name__ == "__main__":
    app.run(host="0.0.0.0")
