import React from 'react';
import {renderToString} from 'react-dom/server';
import {TrueScrubClient} from 'client/TrueScrubClient.js';


describe('TrueScrubClient', () => {
  it('renders and maps root route to HomePage', () => {
    const html = renderToString(<TrueScrubClient/>);
    expect(html).toContain('TrueScrub™');
    expect(html).toContain('Leaderboard');
  });
});
