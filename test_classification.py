"""Test email classification system"""

import sys

sys.path.insert(0, "/home/harshtripathi/Desktop/genios-brain")

from app.ingestion.email_classifier import classify_email, parse_system_email

print("=" * 70)
print("Testing Email Classification System v1.1")
print("=" * 70)

# Test 1: SYSTEM email
print("\n1️⃣ Testing SYSTEM classification...")
result = classify_email(
    subject="Your GST Return for Q2 FY2023-24 filed successfully",
    sender_email="gst@gov.in",
    body="Your GST return has been successfully filed. ARN: AA1234567890123",
)
assert result == "SYSTEM", f"Expected SYSTEM, got {result}"
print(f"✅ Classification: {result}")

# Test 2: DISCARD email
print("\n2️⃣ Testing DISCARD classification...")
result = classify_email(
    subject="Weekly Newsletter",
    sender_email="noreply@newsletter.com",
    body="This week's top stories...",
)
assert result == "DISCARD", f"Expected DISCARD, got {result}"
print(f"✅ Classification: {result}")

# Test 3: WEAK email
print("\n3️⃣ Testing WEAK classification...")
result = classify_email(
    subject="Thanks!",
    sender_email="john@example.com",
    body="Got it, thanks!",  # 3 words < 25
)
assert result == "WEAK", f"Expected WEAK, got {result}"
print(f"✅ Classification: {result}")

# Test 4: STRONG email
print("\n4️⃣ Testing STRONG classification...")
result = classify_email(
    subject="Series A Planning Discussion",
    sender_email="investor@vc.com",
    body="I'd like to discuss your Series A fundraising plans. Can we schedule a call next week? I have some thoughts on valuation and investor network that might help."
    * 2,
)
assert result == "STRONG", f"Expected STRONG, got {result}"
print(f"✅ Classification: {result}")

# Test 5: SYSTEM parsing - GST
print("\n5️⃣ Testing GST parsing...")
parsed = parse_system_email(
    subject="Your GST Return for Q2 FY2023-24 filed successfully",
    body="Your GST return has been successfully filed. ARN: AA1234567890123 Period: Q2",
    sender_email="gst@gov.in",
)
assert parsed["type"] == "GST"
assert parsed["status"] == "FILED"
assert parsed["metadata"]["arn"] == "AA1234567890123"
assert parsed["metadata"]["period"] == "Q2"
print(
    f"✅ Parsed GST: type={parsed['type']}, status={parsed['status']}, arn={parsed['metadata']['arn']}, period={parsed['metadata']['period']}"
)

# Test 6: SYSTEM parsing - Payment
print("\n6️⃣ Testing Payment parsing...")
parsed = parse_system_email(
    subject="Payment of ₹12,500 to Razorpay confirmed",
    body="Payment of ₹12,500 has been successfully processed to Razorpay",
    sender_email="payments@razorpay.com",
)
assert parsed["type"] == "PAYMENT"
assert parsed["status"] == "CONFIRMED"
assert parsed["metadata"]["amount"] == "12500"
assert "Razorpay" in parsed["metadata"]["vendor"]
print(
    f"✅ Parsed Payment: type={parsed['type']}, amount={parsed['metadata']['amount']}, vendor={parsed['metadata']['vendor']}"
)

print("\n" + "=" * 70)
print("✅ All classification tests PASSED!")
print("=" * 70)
