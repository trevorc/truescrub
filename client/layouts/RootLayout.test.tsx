import React from 'react';
import {renderToString} from 'react-dom/server';
import {MemoryRouter, Route, Routes} from 'react-router-dom';
import {RootLayout} from 'client/layouts/RootLayout';

jest.mock('client/components/Navbar.js', () => ({
  Navbar: () => 'Mock Navbar'
}));

jest.mock('client/components/Footer.js', () => ({
  Footer: () => 'Mock Footer'
}));

describe('RootLayout', () => {
  it('renders the layout with Navbar, Footer, and Outlet content', () => {
    const html = renderToString(
        <MemoryRouter initialEntries={['/']}>
          <Routes>
            <Route element={<RootLayout/>}>
              <Route path="/" element={<div data-testid="content">Page Content</div>}/>
            </Route>
          </Routes>
        </MemoryRouter>
    );

    expect(html).toContain('Mock Navbar');
    expect(html).toContain('Mock Footer');
    expect(html).toContain('Page Content');
    expect(html).toContain('flex-col min-h-screen');
  });
});
