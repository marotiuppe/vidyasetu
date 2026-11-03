import { MR_PRIVACY } from './mr.privacy';
import { MR_APP } from './mr.app';
import { MR_ADMIN } from './mr.admin';
import { MR_STUDENTS_LIST } from './mr.students-list';
import { MR_STUDENTS_FORM } from './mr.students-form';
import { MR_OPS } from './mr.ops';
import { MR_FEES_DAILY } from './mr.fees-daily';
import { MR_FEES_SETUP } from './mr.fees-setup';
import { MR_PUBLIC } from './mr.public';
import { MR_ADMISSIONS } from './mr.admissions';
import { MR_PROMOTION } from './mr.promotion';
import { MR_FEES_TOOLS } from './mr.fees-tools';
import { MR_TOOLS } from './mr.tools';
import { MR_EXAMS } from './mr.exams';

/** Marathi UI strings. Missing keys fall back to English. Server setting labels use `settings.<key>`. */
export const MR: Record<string, string> = {
  ...MR_PRIVACY,
  ...MR_APP,
  ...MR_ADMIN,
  ...MR_STUDENTS_LIST,
  ...MR_STUDENTS_FORM,
  ...MR_OPS,
  ...MR_FEES_DAILY,
  ...MR_FEES_SETUP,
  ...MR_PUBLIC,
  ...MR_ADMISSIONS,
  ...MR_PROMOTION,
  ...MR_FEES_TOOLS,
  ...MR_TOOLS,
  ...MR_EXAMS,
  'nav.settings': 'सेटिंग्ज',
  'settings.choice.en': 'English',
  'settings.choice.mr': 'मराठी',
  'settings.title': 'सेटिंग्ज',
  'settings.subtitle':
    'पोर्टल तुमच्यासाठी, तुमच्या शाखेसाठी, शाळेसाठी किंवा प्लॅटफॉर्मसाठी कसे चालेल ते बदला.',
  'settings.subtitle.personal': 'तुमच्या स्वतःच्या पसंती.',
  'settings.loading': 'सेटिंग्ज लोड होत आहेत…',
  'settings.empty': 'शोधाशी जुळणारी सेटिंग्ज नाहीत.',
  'settings.none': 'येथे अजून सेटिंग्ज नाहीत.',
  'settings.tabs': 'सेटिंग्जची पातळी',
  'settings.level.platform': 'प्लॅटफॉर्म',
  'settings.level.school': 'शाळा',
  'settings.level.branch': 'शाखा',
  'settings.level.user': 'माझी सेटिंग्ज',
  'settings.search': 'सेटिंग्ज शोधा',
  'settings.search.placeholder': 'नाव किंवा मदत मजकुराने शोधा',
  'settings.pickSchool': 'शाळा',
  'settings.pickBranch': 'शाखा',
  'settings.pickSchool.prompt': 'सेटिंग्ज पाहण्यासाठी शाळा निवडा.',
  'settings.pickBranch.prompt': 'सेटिंग्ज पाहण्यासाठी शाखा निवडा.',
  'settings.choose': 'निवडा…',
  'settings.group.toggle': 'हा गट दाखवा किंवा लपवा',
  'settings.source.own': 'स्वतःची किंमत',
  'settings.source.branch': 'शाखेकडून',
  'settings.source.school': 'शाळेकडून',
  'settings.source.platform': 'प्लॅटफॉर्मकडून',
  'settings.source.env': 'सर्व्हर .env मधून',
  'settings.source.default': 'डीफॉल्ट',
  'settings.changedBy': '{name} यांनी {date} रोजी बदलले',
  'settings.changedAt': '{date} रोजी बदलले',
  'settings.save': 'जतन करा',
  'settings.saving': 'जतन होत आहे…',
  'settings.saved': 'जतन केले.',
  'settings.reset': 'डीफॉल्टवर आणा',
  'settings.resetDone': 'डीफॉल्टवर आणले.',
  'settings.readonly': 'फक्त वाचनीय',
  'settings.on': 'चालू',
  'settings.off': 'बंद',
  'settings.set': 'सेट आहे',
  'settings.notSet': 'सेट नाही',
  'settings.secret.replace': 'नवीन किंमत',
  'settings.secret.placeholder': 'बदलण्यासाठी नवीन किंमत लिहा',
  'settings.secret.clear': 'काढून टाका',
  'settings.secret.cleared': 'काढून टाकले.',
  'settings.secret.never': 'जतन केलेली किंमत कधीही दाखवली जात नाही.',
  'settings.range': 'परवानगी असलेली मर्यादा: {min} ते {max}.',
  'settings.test': 'चाचणी पाठवा',
  'settings.testing': 'चाचणी सुरू आहे…',
  'settings.test.ok': 'चाचणी यशस्वी',
  'settings.test.fail': 'चाचणी अयशस्वी',
  'settings.error.load': 'सेटिंग्ज लोड करता आल्या नाहीत.',
  'settings.my.language.hint': 'जतन करताच पोर्टलची भाषा बदलेल.',
  'settings.my.password': 'पासवर्ड बदला',
  'settings.my.passwordHelp': 'तुमच्या खात्यासाठी नवीन पासवर्ड निवडा.',
  'settings.profile.link': 'साइन-इन लॉकआउट आणि शाळेचे इतर नियम आता सेटिंग्जमध्ये आहेत.',
  'settings.profile.open': 'सेटिंग्ज उघडा',
  'legal.school': 'शाळा',
  'legal.schoolGrievance': 'या शाळेचा तक्रार संपर्क',
  'legal.schoolMissing': 'या शाळेने अजून तक्रार तपशील भरलेले नाहीत.',
  // Server-defined settings (label by key); others fall back to the server's English label.
  'settings.user.language': 'भाषा',
  'settings.security.login_max_attempts': 'परवानगी असलेले चुकीचे साइन-इन प्रयत्न',
  'settings.security.login_lockout_minutes': 'लॉकआउट वेळ (मिनिटे)',
  'settings.group.Security': 'सुरक्षा',
  'settings.group.Personal': 'वैयक्तिक',
  'settings.group.Language': 'भाषा',
};
