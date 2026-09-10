-- Credits become divisible: the balance is now stored in POINTS, 100 points = 1 credit.
--
-- Reading one email costs 0.2 credits and one attachment page 0.3 — units far smaller than a
-- question. An integer credit cannot express either: rounded down every ingestion is free, and
-- rounded up one email costs as much as one question. Points are to credits what paise are to
-- rupees, so every balance and ledger row stays a whole number and no float ever reaches the
-- database.
--
-- Existing balances and every historical ledger row are rescaled by the same factor, so a
-- balance_after written last month still reconciles against the balance it produced.
update orgs set credits = credits * 100, topup_credits = topup_credits * 100;
update credit_ledger set amount = amount * 100, balance_after = balance_after * 100;
