import {createClient} from "@connectrpc/connect";
import {createGrpcWebTransport} from "@connectrpc/connect-web";
import {HighlightsService} from "proto/highlights_service_pb.js";

const transport = createGrpcWebTransport({
  baseUrl: window.location.origin,
});

export const client = createClient(HighlightsService, transport);
