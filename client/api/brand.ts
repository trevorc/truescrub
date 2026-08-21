import {createQueryOptions} from "@connectrpc/connect-query";
import {getBrandConfig} from "proto/config_service-ConfigService_connectquery.js";
import type {Transport} from "@connectrpc/connect";

export const brandQueryOptions = (transport: Transport) =>
    createQueryOptions(getBrandConfig, {}, {transport});
