import {createQueryOptions} from "@connectrpc/connect-query";
import {getAvailableSeasons} from "proto/season_service-SeasonService_connectquery.js";
import type {Transport} from "@connectrpc/connect";

export const availableSeasonsQueryOptions = (transport: Transport) =>
    createQueryOptions(getAvailableSeasons, {}, {transport});

export function getLatestSeasonId(availableSeasons: number[]): number | undefined {
  return availableSeasons.length > 0 ? availableSeasons[availableSeasons.length - 1] : undefined;
}

export function getLatestSeasonPath(availableSeasons: number[]): string {
  const latest = getLatestSeasonId(availableSeasons);
  return availableSeasons.length > 1 && latest !== undefined ? `/season/${latest}` : "";
}
