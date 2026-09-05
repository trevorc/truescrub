import {Outlet} from "@tanstack/react-router";
import {Navbar} from "client/components/Navbar.js";
import {Footer} from "client/components/Footer.js";
import {useSuspenseQuery} from "@tanstack/react-query";
import {brandQueryOptions} from "client/api/brand.js";
import {useTransport} from "@connectrpc/connect-query";
import {Suspense} from "react";
import {LoadingState} from "client/components/LoadingState.js";

export function RootLayout() {
  const transport = useTransport();
  const {data} = useSuspenseQuery(brandQueryOptions(transport));

  return (
      <div className="flex flex-col min-h-screen w-full pt-6 pb-12 px-4 sm:px-6 lg:px-8">
        <title>{data.siteName}</title>
        <Navbar/>
        <main className="max-w-7xl mx-auto w-full animate-fade-in flex-grow">
          <Suspense fallback={<LoadingState/>}>
            <Outlet/>
          </Suspense>
        </main>
        <Footer/>
      </div>
  );
}
