import {Transport} from "@connectrpc/connect";
import {createGrpcWebTransport} from "@connectrpc/connect-web";
import {QueryClient} from "@tanstack/react-query";

export const transport: Transport = createGrpcWebTransport({
  baseUrl: window.location.origin,
});

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 3,
      refetchOnWindowFocus: false,
    },
  },
});
