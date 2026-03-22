import base64
import logging
import re
from asyncio import Lock
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Annotated, Literal, Optional, overload
from urllib.parse import quote

import aiohttp
import dacite
from sqlalchemy import select
from typing_extensions import deprecated

from lib.sql.sql import SpotifyToken, get_session


class TitaniumSpotifyClient:
    SPOTIFY_URL_REGEX = r"https://open\.spotify\.com/(track|artist|album)/([a-zA-Z0-9]{22})"

    def __init__(self, client_id: str, client_secret: str) -> None:
        self.SPOTIFY_API_BASE = "https://api.spotify.com/v1"
        self.token_lock = Lock()

        self.client_id = client_id
        self.client_secret = client_secret

        self.access_token: str = ""

    @property
    async def __access_token(self) -> str:
        async with self.token_lock:
            async with get_session() as session:
                result = await session.execute(select(SpotifyToken))
                token_entry = result.scalar_one_or_none()

                if not token_entry:
                    logging.debug("Requesting new access token")
                    return await self.__fetch_access_token()

                if (
                    datetime.now(timezone.utc) - token_entry.time_added
                ).total_seconds() >= token_entry.expires_in:
                    logging.debug("Token expired, requesting new token")
                    await session.delete(token_entry)
                    return await self.__fetch_access_token()

            logging.debug("Token is valid")
            return token_entry.token

    async def __fetch_access_token(self) -> str:
        headers = {
            "Authorization": "Basic "
            + base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://accounts.spotify.com/api/token",
                headers=headers,
                data={"grant_type": "client_credentials"},
            ) as response:
                token_json = await response.json()

        async with get_session() as session:
            token_entry = SpotifyToken(
                token=token_json["access_token"], expires_in=token_json["expires_in"]
            )
            session.add(token_entry)

        logging.debug("Fetched token from Spotify")
        return token_json["access_token"]

    @overload
    async def __authed_get_req(
        self, endpoint: str, data: Optional[dict] = None, text: Literal[False] = ...
    ) -> dict: ...
    @overload
    async def __authed_get_req(
        self, endpoint: str, data: Optional[dict] = None, text: Literal[True] = ...
    ) -> str: ...
    async def __authed_get_req(
        self, endpoint: str, data: Optional[dict] = None, text: bool = False
    ) -> dict | str:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.SPOTIFY_API_BASE}{endpoint}",
                data=data,
                headers={"Authorization": f"Bearer {await self.__access_token}"},
            ) as response:
                response.raise_for_status()

                if text:
                    return await response.text()

                return await response.json()

    async def album(self, query: str, market: str = "") -> SpotifyAlbum:
        match = re.search(TitaniumSpotifyClient.SPOTIFY_URL_REGEX, query)
        if match:
            query = match.group(2)

        response = await self.__authed_get_req(
            endpoint=f"/albums/{quote(query)}{f'?market={market}' if market else ''}"
        )
        return dacite.from_dict(data_class=SpotifyAlbum, data=response)

    async def artist(self, query: str, market: str = "") -> SpotifyArtist:
        match = re.search(TitaniumSpotifyClient.SPOTIFY_URL_REGEX, query)
        if match:
            query = match.group(2)

        response = await self.__authed_get_req(
            endpoint=f"/artists/{quote(query)}{f'?market={market}' if market else ''}"
        )
        return dacite.from_dict(data_class=SpotifyArtist, data=response)

    @deprecated("This API endpoint is deprecated")
    async def artist_top_tracks(self, query: str, market: str = "") -> SpotifyArtistTopTracks:
        match = re.search(TitaniumSpotifyClient.SPOTIFY_URL_REGEX, query)
        if match:
            query = match.group(2)

        response = await self.__authed_get_req(
            endpoint=f"/artists/{quote(query)}/top-tracks{f'?market={market}' if market else ''}"
        )
        return dacite.from_dict(data_class=SpotifyArtistTopTracks, data=response)

    async def track(self, query: str, market: str = "") -> SpotifyTrack:
        match = re.search(TitaniumSpotifyClient.SPOTIFY_URL_REGEX, query)
        if match:
            query = match.group(2)

        response = await self.__authed_get_req(
            endpoint=f"/tracks/{quote(query)}{f'?market={market}' if market else ''}"
        )
        return dacite.from_dict(data_class=SpotifyTrack, data=response)

    async def search_albums(
        self,
        query: str,
        market: str = "",
        limit: int = 5,
        offset: int = 0,
    ) -> SpotifyAlbums:
        response = await self.__authed_get_req(
            endpoint=f"/search?q={quote(query)}&type=album"
            f"{f'&market={market}' if market else ''}"
            f"&limit={limit}&offset={offset}"
        )
        return dacite.from_dict(data_class=SpotifyAlbums, data=response["albums"])

    async def search_artists(
        self,
        query: str,
        market: str = "",
        limit: int = 5,
        offset: int = 0,
    ) -> SpotifyArtists:
        response = await self.__authed_get_req(
            endpoint=f"/search?q={quote(query)}&type=artist"
            f"{f'&market={market}' if market else ''}"
            f"&limit={limit}&offset={offset}"
        )
        return dacite.from_dict(data_class=SpotifyArtists, data=response["artists"])

    async def search_tracks(
        self,
        query: str,
        market: str = "",
        limit: int = 5,
        offset: int = 0,
    ) -> SpotifyTracks:
        response = await self.__authed_get_req(
            endpoint=f"/search?q={quote(query)}&type=track"
            f"{f'&market={market}' if market else ''}"
            f"&limit={limit}&offset={offset}"
        )
        return dacite.from_dict(data_class=SpotifyTracks, data=response["tracks"])


@dataclass
class SpotifyBaseObj:
    external_urls: dict[Literal["spotify"], str]
    href: str
    id: str
    name: str
    uri: str


@dataclass
class SpotifyImage:
    url: str
    height: Optional[int]
    width: Optional[int]


@dataclass
class SpotifyCopyright:
    text: str
    type: str


@dataclass
class SpotifyFollowers:
    href: Optional[str]
    total: int


@dataclass
class SpotifySearchObj:
    href: str
    limit: int
    next: Optional[str]
    offset: int
    previous: Optional[str]
    total: int


@dataclass
class SpotifySimplifiedTrack(SpotifyBaseObj):
    type: Literal["track"]

    artists: list[SpotifySimplifiedArtist]
    available_markets: Annotated[list[str], deprecated("This field is deprecated")]
    disc_number: int
    duration_ms: int
    explicit: bool
    is_playable: Optional[bool]
    linked_from: Annotated[Optional[SpotifyBaseObj], deprecated("This field is deprecated")]
    restrictions: Optional[dict[Literal["reason"], Literal["market", "product", "explicit"]]]
    preview_url: Annotated[Optional[str], deprecated("This field is deprecated")]
    track_number: int
    is_local: bool


@dataclass
class SpotifySimplifiedArtist(SpotifyBaseObj):
    type: Literal["artist"]


@dataclass
class SpotifySimplifiedAlbum(SpotifyBaseObj):
    type: Literal["album"]

    album_type: Literal["album", "single", "compilation"]
    total_tracks: int
    available_markets: Annotated[list[str], deprecated("This field is deprecated")]
    images: list[SpotifyImage]
    release_date: str
    release_date_precision: str
    restrictions: Optional[dict[Literal["reason"], Literal["market", "product", "explicit"]]]
    artists: list[SpotifySimplifiedArtist]


@dataclass
class SpotifyTrack(SpotifySimplifiedTrack):
    type: Literal["track"]

    album: SpotifySimplifiedAlbum
    external_ids: Annotated[
        dict[Literal["isrc", "ean", "upc"], str], deprecated("This field is deprecated")
    ]
    popularity: Annotated[int, deprecated("This field is deprecated")]


@dataclass
class SpotifyArtist(SpotifySimplifiedArtist):
    followers: Annotated[Optional[SpotifyFollowers], deprecated("This field is deprecated")]
    genres: Annotated[list[str], deprecated("This field is deprecated")]
    images: list[SpotifyImage]
    popularity: Annotated[int, deprecated("This field is deprecated")]


@dataclass
class SpotifyAlbum(SpotifySimplifiedAlbum):
    tracks: SpotifyAlbumTracks
    copyrights: list[SpotifyCopyright]
    external_ids: Annotated[
        dict[Literal["isrc", "ean", "upc"], str], deprecated("This field is deprecated")
    ]
    genres: Annotated[list[str], deprecated("This field is deprecated")]
    label: Annotated[str, deprecated("This field is deprecated")]
    popularity: Annotated[int, deprecated("This field is deprecated")]


@dataclass
class SpotifyAlbums(SpotifySearchObj):
    items: list[SpotifySimplifiedAlbum]


@dataclass
class SpotifyArtists(SpotifySearchObj):
    items: list[SpotifyArtist]


@dataclass
class SpotifyTracks(SpotifySearchObj):
    items: list[SpotifyTrack]


@dataclass
class SpotifyAlbumTracks(SpotifySearchObj):
    items: list[SpotifySimplifiedTrack]


@dataclass
class SpotifyArtistTopTracks:
    tracks: list[SpotifyTrack]
