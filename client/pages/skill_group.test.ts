import {SkillGroupConfiguration} from 'truescrub/proto/profile_pb.js';
import {skillGroupName} from 'client/pages/skill_group.js';

describe('skill_group', () => {
  let mockConfig: SkillGroupConfiguration;

  beforeEach(() => {
    mockConfig = {
      skillGroups: [
        {lowerBound: 0, name: 'Rank 1', specialName: 'Special 1'},
        {lowerBound: 500, name: 'Rank 2', specialName: 'Special 2'},
        {lowerBound: 1000, name: 'Rank 3', specialName: 'Special 3'},
        {lowerBound: 1500, name: 'Rank 4', specialName: 'Special 4'},
      ]
    } as SkillGroupConfiguration;
  });

  describe('skillGroupName', () => {
    it('returns "Unranked" if the configuration is empty', () => {
      const emptyConfig = {skillGroups: []} as unknown as SkillGroupConfiguration;
      expect(skillGroupName(1000, emptyConfig)).toBe('Unranked');
    });

    it('returns the lowest rank for an MMR below the second tier', () => {
      expect(skillGroupName(0, mockConfig)).toBe('Rank 1');
      expect(skillGroupName(250, mockConfig)).toBe('Rank 1');
      expect(skillGroupName(499, mockConfig)).toBe('Rank 1');
    });

    it('returns exactly on the boundary', () => {
      expect(skillGroupName(500, mockConfig)).toBe('Rank 2');
      expect(skillGroupName(1000, mockConfig)).toBe('Rank 3');
      expect(skillGroupName(1500, mockConfig)).toBe('Rank 4');
    });

    it('returns the highest rank for MMRs well above the final boundary', () => {
      expect(skillGroupName(1501, mockConfig)).toBe('Rank 4');
      expect(skillGroupName(5000, mockConfig)).toBe('Rank 4');
    });

    it('returns special names when requested', () => {
      expect(skillGroupName(250, mockConfig, true)).toBe('Special 1');
      expect(skillGroupName(1000, mockConfig, true)).toBe('Special 3');
      expect(skillGroupName(5000, mockConfig, true)).toBe('Special 4');
    });
  });
});
