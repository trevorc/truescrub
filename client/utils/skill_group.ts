import {SkillGroupConfiguration} from 'truescrub/proto/profile_pb.js';

/**
 * Derives the skill group name for a given MMR from the provided configuration.
 * Uses a binary search over the configured lower bounds to find the appropriate group.
 * 
 * @param mmr The player's MMR
 * @param config The skill group configuration loaded from JSON
 * @param isSpecial Whether to return the special (Easter egg) name
 * @returns The skill group name
 */
export function skillGroupName(mmr: number, config: SkillGroupConfiguration, isSpecial: boolean = false): string {
  if (config.skillGroups.length === 0) {
    return 'Unranked';
  }

  let low = 0;
  let high = config.skillGroups.length - 1;
  let matchIndex = 0;

  // Binary search to find the highest lowerBound that is <= mmr
  // Since skillGroups are sorted from lowest MMR to highest MMR
  while (low <= high) {
    const mid = Math.floor((low + high) / 2);
    if (config.skillGroups[mid].lowerBound <= mmr) {
      matchIndex = mid;
      low = mid + 1; // Look for a higher bound
    } else {
      high = mid - 1;
    }
  }

  const group = config.skillGroups[matchIndex];
  return isSpecial ? group.specialName : group.name;
}
