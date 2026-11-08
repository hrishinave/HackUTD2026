# ClaimTrak Billing System: User Manual

**Lone Star Family Clinic, Billing Office** (fictional demo client)
Revision 3, February 2009. Prepared by the clinic IT contractor.

> This is the manual staff were given in 2009. It has not been updated since. Parts of it no longer match what the system does.

## 1. Purpose

ClaimTrak checks every claim before it goes to a payer. Claims are entered during the day and checked overnight by the batch program CLMEDIT. Each morning, billing clerks work the claims CLMEDIT returned to them.

## 2. Daily routine

1. Enter new claims on the Claim Entry screen.
2. The overnight batch checks every claim.
3. In the morning, open the Returned Claims list and fix each returned claim.
4. Fixed claims go back into the next overnight batch.

## 3. What happens to a claim

Every claim gets one of two results:

| Result | Meaning | What you do |
|---|---|---|
| Accepted | Sent to the payer | Nothing |
| Returned | Something is wrong | Fix it from the Returned Claims list |

## 4. Edits the system applies

### 4.1 Required fields
Patient ID, procedure code, date of service and payer must be filled. Claims with missing fields cannot be saved.

### 4.2 Timely filing
Claims must be filed within **180 days** of the date of service. Claims filed later are returned with reason TF01 and must be appealed with the payer.

### 4.3 Duplicate claims
A claim for the same patient, date of service and procedure as an earlier claim is returned with reason DP01. Check whether the first claim was paid before resubmitting.

### 4.4 Modifier 25
When an evaluation and management visit is billed on the same day as a procedure, the visit line **must** carry modifier 25. Claims without it are returned with reason MD25.

## 5. Prior authorization

### 5.1 Recording the authorization
Some procedures (most imaging, some injections) need prior authorization from the payer. When you receive the authorization, enter the authorization number in the **PA-NUM** field on the Claim Entry screen. Claims that need authorization and have no PA-NUM are returned with reason PA01.

### 5.2 Faxed authorizations
Payers often fax the authorization. Keep the fax in the patient folder.

## 6. Paper claims

Paper claims are no longer accepted. All claims must be entered electronically.

## 7. Help

Call the IT contractor during business hours. After hours, leave the claim for the next day.
