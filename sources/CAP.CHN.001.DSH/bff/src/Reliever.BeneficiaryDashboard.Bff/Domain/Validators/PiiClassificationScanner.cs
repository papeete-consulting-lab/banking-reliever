using System.Linq;
using System.Text.Json.Nodes;

namespace Reliever.BeneficiaryDashboard.Bff.Domain.Validators;

/// <summary>
/// INV.DSH.001 — PII-exclusion gate.
/// The dashboard projection MUST NOT contain any PII (per
/// ADR-TECH-STRAT-004 low-PII lane + process/CAP.CHN.001.DSH/aggregates.yaml).
///
/// As of v0.2.0 of the upstream schemas, none of the producer RVTs
/// declare a <c>pii_classification</c> annotation. The dashboard
/// therefore enforces the invariant using a *deny-list* of property
/// names commonly used for PII fields. If ANY of these property names
/// appears anywhere in the inbound payload (top-level or nested), the
/// scanner returns false and the consumer DLQs the payload — this is
/// stricter than necessary by design: a payload that "looks like" it
/// might carry PII is rejected to surface the upstream contract
/// regression, never silently absorbed into the channel.
///
/// The deny-list mirrors the URBA constraints captured in
/// ADR-TECH-TACT-001 ("pii-exclusion"): names, contact details,
/// dates of birth, raw merchant names, civic IDs.
/// </summary>
public static class PiiClassificationScanner
{
    private static readonly HashSet<string> DenyListedPropertyNames = new(StringComparer.OrdinalIgnoreCase)
    {
        "first_name", "firstName",
        "last_name", "lastName",
        "full_name", "fullName",
        "given_name", "givenName",
        "family_name", "familyName",
        "name",                       // bare 'name' is too risky on a low-PII lane
        "date_of_birth", "dateOfBirth", "dob",
        "email", "email_address", "emailAddress",
        "phone", "phone_number", "phoneNumber", "msisdn",
        "address", "postal_address", "postalAddress",
        "street", "street_address", "streetAddress",
        "city", "postal_code", "postalCode", "zipcode", "zip_code",
        "national_id", "nationalId", "ssn",
        "passport_number", "passportNumber",
        "iban", "account_number", "accountNumber",
        "card_number", "cardNumber", "pan",
        "merchant_name", "merchantName",      // raw merchant name — only merchant_label (semantic) is allowed
        "beneficiary_record", "beneficiaryRecord",
        "contact_details", "contactDetails",
        "internal_id", "internalId",          // canonical beneficiary id from CAP.SUP.002 — channel must NOT carry it
    };

    /// <summary>
    /// Returns true if no deny-listed property is present anywhere in
    /// the payload. Sets <paramref name="violatingPath"/> to the dotted
    /// JSON path of the first detected PII field when it returns false.
    /// </summary>
    public static bool IsPiiFree(JsonNode? payload, out string? violatingPath)
    {
        violatingPath = null;
        if (payload is null)
        {
            return true;
        }
        return Scan(payload, "$", ref violatingPath);
    }

    private static bool Scan(JsonNode node, string path, ref string? violatingPath)
    {
        switch (node)
        {
            case JsonObject obj:
                foreach (var (key, child) in obj)
                {
                    if (DenyListedPropertyNames.Contains(key))
                    {
                        violatingPath = $"{path}.{key}";
                        return false;
                    }
                    if (child is not null && !Scan(child, $"{path}.{key}", ref violatingPath))
                    {
                        return false;
                    }
                }
                return true;

            case JsonArray arr:
                for (var i = 0; i < arr.Count; i++)
                {
                    var child = arr[i];
                    if (child is not null && !Scan(child, $"{path}[{i}]", ref violatingPath))
                    {
                        return false;
                    }
                }
                return true;

            default:
                return true;
        }
    }
}
