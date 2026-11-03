import { EN_PRIVACY } from './en.privacy';
import { EN_APP } from './en.app';
import { EN_ADMIN } from './en.admin';
import { EN_STUDENTS_LIST } from './en.students-list';
import { EN_STUDENTS_FORM } from './en.students-form';
import { EN_OPS } from './en.ops';
import { EN_FEES_DAILY } from './en.fees-daily';
import { EN_FEES_SETUP } from './en.fees-setup';
import { EN_PUBLIC } from './en.public';
import { EN_ADMISSIONS } from './en.admissions';
import { EN_PROMOTION } from './en.promotion';
import { EN_FEES_TOOLS } from './en.fees-tools';
import { EN_TOOLS } from './en.tools';
import { EN_EXAMS } from './en.exams';

/** English UI strings for the Settings area. English is the fallback for every language. */
export const EN: Record<string, string> = {
  ...EN_PRIVACY,
  ...EN_APP,
  ...EN_ADMIN,
  ...EN_STUDENTS_LIST,
  ...EN_STUDENTS_FORM,
  ...EN_OPS,
  ...EN_FEES_DAILY,
  ...EN_FEES_SETUP,
  ...EN_PUBLIC,
  ...EN_ADMISSIONS,
  ...EN_PROMOTION,
  ...EN_FEES_TOOLS,
  ...EN_TOOLS,
  ...EN_EXAMS,
  'nav.settings': 'Settings',
  'settings.choice.en': 'English',
  'settings.choice.mr': 'मराठी',
  'settings.title': 'Settings',
  'settings.subtitle':
    'Change how the portal works for you, your branch, your school or the platform.',
  'settings.subtitle.personal': 'Your own preferences.',
  'settings.loading': 'Loading settings…',
  'settings.empty': 'No settings match your search.',
  'settings.none': 'There are no settings here yet.',
  'settings.tabs': 'Settings level',
  'settings.level.platform': 'Platform',
  'settings.level.school': 'School',
  'settings.level.branch': 'Branch',
  'settings.level.user': 'My settings',
  'settings.search': 'Search settings',
  'settings.search.placeholder': 'Search by name or help text',
  'settings.pickSchool': 'School',
  'settings.pickBranch': 'Branch',
  'settings.pickSchool.prompt': 'Choose a school to see its settings.',
  'settings.pickBranch.prompt': 'Choose a branch to see its settings.',
  'settings.choose': 'Choose…',
  'settings.group.toggle': 'Show or hide this group',
  'settings.source.own': 'Own value',
  'settings.source.branch': 'Inherited from branch',
  'settings.source.school': 'Inherited from school',
  'settings.source.platform': 'Inherited from platform',
  'settings.source.env': 'From server .env',
  'settings.source.default': 'Default',
  'settings.changedBy': 'Last changed by {name} on {date}',
  'settings.changedAt': 'Last changed on {date}',
  'settings.save': 'Save',
  'settings.saving': 'Saving…',
  'settings.saved': 'Saved.',
  'settings.reset': 'Reset to default',
  'settings.resetDone': 'Reset to default.',
  'settings.readonly': 'Read-only',
  'settings.on': 'On',
  'settings.off': 'Off',
  'settings.set': 'Set',
  'settings.notSet': 'Not set',
  'settings.secret.replace': 'New value',
  'settings.secret.placeholder': 'Type a new value to replace it',
  'settings.secret.clear': 'Clear',
  'settings.secret.cleared': 'Cleared.',
  'settings.secret.never': 'The stored value is never shown.',
  'settings.range': 'Allowed range: {min} to {max}.',
  'settings.test': 'Send test',
  'settings.testing': 'Testing…',
  'settings.test.ok': 'Test passed',
  'settings.test.fail': 'Test failed',
  'settings.error.load': 'Settings could not be loaded.',
  'settings.my.language.hint': 'The language of the portal changes as soon as you save.',
  'settings.my.password': 'Change password',
  'settings.my.passwordHelp': 'Choose a new password for your account.',
  'settings.profile.link': 'Sign-in lockout and other school rules are now in Settings.',
  'settings.profile.open': 'Open settings',
  'legal.school': 'School',
  'legal.schoolGrievance': 'Grievance contact of this school',
  'legal.schoolMissing': 'This school has not entered its grievance details yet.',
};
