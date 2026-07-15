import {getSkillGroupDisplayBounds} from 'client/pages/SkillGroupsPage.js';

describe('SkillGroupsPage Utilities', () => {
  describe('getSkillGroupDisplayBounds', () => {
    it('handles the lowest rank with negative infinity', () => {
      const group = {lowerBound: Number.NEGATIVE_INFINITY};
      const nextGroup = {lowerBound: 0};
      
      const bounds = getSkillGroupDisplayBounds(group, nextGroup);
      
      expect(bounds.lowerBound).toBe('-∞');
      expect(bounds.upperBound).toBe('0');
    });

    it('handles a middle rank with standard bounds', () => {
      const group = {lowerBound: 1000};
      const nextGroup = {lowerBound: 1500};
      
      const bounds = getSkillGroupDisplayBounds(group, nextGroup);
      
      expect(bounds.lowerBound).toBe('1000');
      expect(bounds.upperBound).toBe('1500');
    });

    it('handles the highest rank with infinity', () => {
      const group = {lowerBound: 2000};
      
      const bounds = getSkillGroupDisplayBounds(group, undefined);
      
      expect(bounds.lowerBound).toBe('2000');
      expect(bounds.upperBound).toBe('∞');
    });
  });
});
