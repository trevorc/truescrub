/// <reference types="jest" />
import {calculatePercentileBounds, erf} from 'client/pages/LeaderboardPage.js';

describe('LeaderboardPage Logic', () => {
  describe('erf', () => {
    it('should calculate the error function correctly for known values', () => {
      expect(erf(0)).toBeCloseTo(0, 4);
      // erf(1) ≈ 0.8427 (using our approximation, it's 0.8429)
      expect(erf(1)).toBeCloseTo(0.8429, 3);

      // erf(-1) ≈ -0.8427
      expect(erf(-1)).toBeCloseTo(-0.8429, 3);
      expect(erf(10)).toBeCloseTo(1, 4);
    });
  });

  describe('calculatePercentileBounds', () => {
    it('should calculate 50th percentile for the global average (mu = 1000, sigma = 250) when zScore = 0', () => {
      const {lower, upper} = calculatePercentileBounds(1000, 250, 0);
      expect(lower).toBeCloseTo(0.5, 4);
      expect(upper).toBeCloseTo(0.5, 4);
    });

    it('should calculate percentiles correctly for zScore = 2.0 (95.45% confidence)', () => {
      const {lower, upper} = calculatePercentileBounds(1500, 250, 2.0);
      expect(lower).toBeCloseTo(0.5, 4); // 50th percentile
      expect(upper).toBeGreaterThan(0.999);
    });

    it('should calculate percentiles correctly for zScore = 1.0 (68.27% confidence)', () => {
      const {lower, upper} = calculatePercentileBounds(1000, 250, 1.0);
      expect(lower).toBeCloseTo(0.1586, 3);
      expect(upper).toBeCloseTo(0.8413, 3);
    });

    it('should calculate percentiles for a very highly skilled player', () => {
      const {lower, upper} = calculatePercentileBounds(1750, 250, 2.0);
      // Lower bound is 1250 (mu + 1 sigma). Percentile for 1250 should be ~84.1%
      expect(lower).toBeCloseTo(0.8413, 3);
      // Upper bound is 2250 (mu + 5 sigma). Percentile for 2250 should be ~99.999%
      expect(upper).toBeCloseTo(1.0, 3);
    });

    it('should calculate percentiles for a very unskilled player', () => {
      const {lower, upper} = calculatePercentileBounds(250, 250, 2.0);
      // Upper bound is 750 (mu - 1 sigma). Percentile for 750 should be ~15.86%
      expect(upper).toBeCloseTo(0.1586, 3);
      // Lower bound is -250 (mu - 5 sigma). Percentile for -250 should be ~0.0%
      expect(lower).toBeCloseTo(0.0, 3);
    });
  });
});
