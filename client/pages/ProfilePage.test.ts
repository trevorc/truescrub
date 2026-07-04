import {getLocalTimezoneOffset, calculateAchievements, AchievementConfig, AchievementProgress} from 'client/pages/ProfilePage.js';

describe('ProfilePage utilities', () => {
  describe('getLocalTimezoneOffset', () => {
    it('formats a negative timezone offset correctly (e.g., UTC-4)', () => {
      const mockDate = new Date();
      mockDate.getTimezoneOffset = jest.fn(() => 240);
      expect(getLocalTimezoneOffset(mockDate)).toBe('-04:00');
    });

    it('formats a positive timezone offset correctly (e.g., UTC+5:30)', () => {
      const mockDate = new Date();
      mockDate.getTimezoneOffset = jest.fn(() => -330);
      expect(getLocalTimezoneOffset(mockDate)).toBe('+05:30');
    });

    it('formats UTC (0 offset) correctly', () => {
      const mockDate = new Date();
      mockDate.getTimezoneOffset = jest.fn(() => 0);
      expect(getLocalTimezoneOffset(mockDate)).toBe('+00:00');
    });
  });

  describe('calculateAchievements', () => {
    let mockConfig: AchievementConfig[];

    beforeEach(() => {
      mockConfig = [
        {
          id: 'wins',
          name: 'Wins',
          tiers: [
            {name: 'Bronze', threshold: 10},
            {name: 'Silver', threshold: 50},
            {name: 'Gold', threshold: 100},
          ]
        },
        {
          id: 'headshots',
          name: 'Headshots',
          tiers: [
            {name: 'Sharpshooter', threshold: 100},
            {name: 'Assassin', threshold: 500},
          ]
        }
      ];
    });

    it('returns empty results for a player with no progress', () => {
      const progress: AchievementProgress[] = [];
      const result = calculateAchievements(mockConfig, progress);
      
      expect(result.totalTiers).toBe(5);
      expect(result.earnedCount).toBe(0);
      
      const wins = result.enrichedAchievements.find(a => a.id === 'wins')!;
      expect(wins.currentValue).toBe(0);
      expect(wins.highestEarnedTier).toBeUndefined();
    });

    it('correctly calculates tiers for partial progress', () => {
      const progress: AchievementProgress[] = [
        {achievementId: 'wins', currentValue: 75},
        {achievementId: 'headshots', currentValue: 100}
      ];
      const result = calculateAchievements(mockConfig, progress);
      
      expect(result.totalTiers).toBe(5);
      expect(result.earnedCount).toBe(3);

      const wins = result.enrichedAchievements.find(a => a.id === 'wins')!;
      expect(wins.currentValue).toBe(75);
      expect(wins.highestEarnedTier?.name).toBe('Silver');
      
      const headshots = result.enrichedAchievements.find(a => a.id === 'headshots')!;
      expect(headshots.currentValue).toBe(100);
      expect(headshots.highestEarnedTier?.name).toBe('Sharpshooter');
    });
  });
});
