*> ================================================================
*> CLAIMREC.cpy   Claim record layout, fixed width, 300 bytes
*> Lone Star Family Clinic billing (fictional demo client)
*>
*> Rev 2003-04  Original layout.
*> Rev 2006-09  Form type P (paper claims) RETIRED. Every claim now
*>              arrives electronic (form type E). OCR batch shut down.
*> Rev 2009-02  CLM-PA-NUM added for the prior-authorization number.
*> Rev 2011-06  CLM-EM-SAME-DAY added for the modifier 25 edit.
*> ================================================================
 01  CLAIM-REC.
     05  CLM-ID                  PIC X(10).
     05  CLM-PATIENT-ID          PIC X(10).
     05  CLM-PROC-CODE           PIC X(5).
     05  CLM-MODIFIER            PIC X(2).
     05  CLM-EM-SAME-DAY         PIC X(1).
         *> Y = evaluation/management visit billed the same day
     05  CLM-DOS                 PIC 9(8).
         *> date of service, YYYYMMDD
     05  CLM-FILE-DATE           PIC 9(8).
         *> date the claim is filed, YYYYMMDD
     05  CLM-COVERAGE-CHG-DATE   PIC 9(8).
         *> date the patient's coverage last changed, zeros if none
     05  CLM-PAYER-ID            PIC X(5).
     05  CLM-PA-REQUIRED         PIC X(1).
         *> Y = procedure needs prior authorization
     05  CLM-PA-NUM              PIC X(12).
     05  CLM-FORM-TYPE           PIC X(1).
         *> E = electronic. P = paper (retired 2006, see header)
     05  CLM-NOTES               PIC X(200).
     05  CLM-ROUTE               PIC X(1).
         *> set by CLMEDIT: A accept, R reject to clerk, Q clerk queue
     05  CLM-REJECT-CODE         PIC X(4).
     05  FILLER                  PIC X(24).
