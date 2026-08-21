import {formatMatchDayString, parseMatchDayString} from 'client/pages/AccoladesPage.js';
import {create} from "@bufbuild/protobuf";
import {DateSchema} from 'proto/common_pb.js';

describe('AccoladesPage Utilities', () => {
  describe('formatMatchDayString', () => {
    it('pads single-digit months and days with leading zeros', () => {
      expect(formatMatchDayString(create(DateSchema, {
        year: 2023,
        month: 5,
        day: 9
      }))).toBe('2023-05-09');
    });

    it('does not pad double-digit months and days', () => {
      expect(formatMatchDayString(create(DateSchema, {
        year: 2024,
        month: 12,
        day: 25
      }))).toBe('2024-12-25');
    });
  });

  describe('parseMatchDayString', () => {
    it('returns undefined for null input', () => {
      expect(parseMatchDayString(null)).toBeUndefined();
    });

    it('returns undefined for invalid format strings', () => {
      expect(parseMatchDayString('20230509')).toBeUndefined();
      expect(parseMatchDayString('2023-05')).toBeUndefined();
      expect(parseMatchDayString('invalid-string')).toBeUndefined();
    });

    it('correctly parses a valid YYYY-MM-DD string', () => {
      expect(parseMatchDayString('2023-05-09')).toEqual(create(DateSchema, {
        year: 2023,
        month: 5,
        day: 9
      }));
    });

    it('correctly parses a YYYY-MM-DD string with double-digits', () => {
      expect(parseMatchDayString('2024-12-25')).toEqual(create(DateSchema, {
        year: 2024,
        month: 12,
        day: 25
      }));
    });
  });
});
