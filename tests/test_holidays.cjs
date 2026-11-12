const assert=require('node:assert/strict');
const {isJapaneseHoliday}=require('../holidays.js');
const publicHolidays2026=[
  '2026-01-01','2026-01-12','2026-02-11','2026-02-23',
  '2026-03-20','2026-04-29','2026-05-03','2026-05-04',
  '2026-05-05','2026-05-06','2026-07-20','2026-08-11',
  '2026-09-21','2026-09-22','2026-09-23','2026-10-12',
  '2026-11-03','2026-11-23'
];
for(const day of publicHolidays2026){
  assert.equal(isJapaneseHoliday(day),true,day+' should be a holiday');
}
for(const day of ['2026-01-02','2026-03-21','2026-06-01','2026-11-12','2026-12-31']){
  assert.equal(isJapaneseHoliday(day),false,day+' should not be a holiday');
}
// 2027 spring equinox is Sunday; Monday is the substitute holiday.
assert.equal(isJapaneseHoliday('2027-03-21'),true);
assert.equal(isJapaneseHoliday('2027-03-22'),true);
assert.equal(isJapaneseHoliday('2027-03-23'),false);
console.log('Japanese holiday tests passed');
