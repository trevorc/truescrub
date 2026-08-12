import {Outlet} from "react-router-dom";
import {Navbar} from "client/components/Navbar.js";
import {Footer} from "client/components/Footer.js";

export function RootLayout() {
  return (
      <div className="flex flex-col min-h-screen w-full pt-6 pb-12 px-4 sm:px-6 lg:px-8">
        <Navbar/>
        <main className="max-w-7xl mx-auto w-full animate-fade-in flex-grow">
          <Outlet/>
        </main>
        <Footer/>
      </div>
  );
}
