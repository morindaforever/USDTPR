/**
 * Help center FAQ data (§24–§26). Structured content kept in one data
 * module — not a CMS. Answers describe how the platform actually behaves.
 */

export interface FaqItem {
  question: string;
  answer: string;
}

export interface FaqCategory {
  id: string;
  title: string;
  items: FaqItem[];
}

export const FAQ_CATEGORIES: FaqCategory[] = [
  {
    id: 'getting-started',
    title: 'Getting Started',
    items: [
      {
        question: 'What is this platform?',
        answer:
          'It is a USDT-themed platform for managing accounts. Wallets, deposits, VIP plans, rewards, referrals, and withdrawals are all available features.',
      },
      {
        question: 'How do I create an account?',
        answer:
          'Use the Sign up page with your email, phone number, and a strong password. If a friend invited you, paste their referral code in the referral field during signup.',
      },
    ],
  },
  {
    id: 'deposits',
    title: 'Deposits',
    items: [
      {
        question: 'How do I deposit?',
        answer:
          'Open the Deposit page, pick a supported network, and submit the transaction hash plus amount of your USDT transfer to the displayed address. Every deposit request is manually reviewed and approved by the team before your balance changes.',
      },
      {
        question: 'Why is my deposit still pending?',
        answer:
          'Deposits stay PENDING until an administrator verifies the transfer on-chain and approves it. Rejected requests show a reason in your deposit history. Your balance is only credited after approval.',
      },
    ],
  },
  {
    id: 'vip',
    title: 'VIP Plans',
    items: [
      {
        question: 'How do I purchase a VIP plan?',
        answer:
          'Open the VIP page, choose a plan, and confirm. The investment amount is debited from your withdrawable balance through the wallet ledger, and the plan terms (rate, target, duration) are snapshotted on the purchase record.',
      },
      {
        question: 'How are rewards displayed?',
        answer:
          'Rewards are calculated by the daily reward engine according to each plan\'s configured terms and are credited to your withdrawable balance with a full ledger entry.',
      },
      {
        question: 'What does "target" mean on a plan?',
        answer:
          'When the total credited rewards for a purchase reach its target amount, the purchase completes automatically and no further rewards accrue for it.',
      },
    ],
  },
  {
    id: 'referrals',
    title: 'Referrals',
    items: [
      {
        question: 'How do I use my referral link?',
        answer:
          'Copy your code or link from the Account or Team page and share it. When someone signs up through it, they join your team and you earn a commission on their qualifying activity, paid through the ledger.',
      },
      {
        question: 'How many levels does my team have?',
        answer:
          'The team tree covers multiple levels (see the Team page for your level counts). Commission rates per level are shown there.',
      },
    ],
  },
  {
    id: 'withdrawals',
    title: 'Withdrawals',
    items: [
      {
        question: 'How do I withdraw?',
        answer:
          'Open the Withdraw page, select a network, enter your destination address and amount, then confirm. The requested amount is locked immediately, and an administrator reviews the request before any payout is marked complete.',
      },
      {
        question: 'Why was my balance locked after requesting a withdrawal?',
        answer:
          'Locking guarantees the funds are reserved for your request while it awaits review. If the request is rejected or processing fails, the exact amount is released back to your withdrawable balance automatically.',
      },
      {
        question: 'What are the fees and minimums?',
        answer:
          'The current minimum and network fee are shown on the Withdraw page before you confirm. The figures you see at confirmation are snapshotted onto the request and never change afterwards.',
      },
    ],
  },
  {
    id: 'account-security',
    title: 'Account & Security',
    items: [
      {
        question: 'How do I change my password?',
        answer:
          'Use Account → Change password. After a successful change, all other sessions are signed out for your security.',
      },
      {
        question: 'I forgot my password. What now?',
        answer:
          'Use the Forgot password link on the login page. A time-limited reset link is issued through the existing reset flow.',
      },
      {
        question: 'Can I change my email or user ID?',
        answer:
          'Your user ID and referral code are permanent. Your email is fixed on the account page — contact support through the Support page if you need it changed.',
      },
    ],
  },
];
