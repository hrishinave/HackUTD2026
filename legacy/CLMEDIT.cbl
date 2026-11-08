>>SOURCE FORMAT FREE
*> ================================================================
*> CLMEDIT   Claims edit batch
*> Lone Star Family Clinic billing office (fictional demo client)
*>
*> Written 2003. Last functional change 2011 (change request CR-4471).
*> Reads CLAIMSIN, applies the edits below in order, and writes
*> CLAIMSOUT with a route on every claim:
*>   A = accept, send to payer
*>   R = reject back to the billing clerk (reason in CLM-REJECT-CODE)
*>   Q = hold in the clerk queue for a manual check
*>
*> Edits (paragraph, rule):
*>   2100-PA-SCAN         prior authorization reference in notes
*>   2200-TIMELY-FILING   filing limit after date of service
*>   2300-MODIFIER-CHECK  modifier 25 on same-day E/M
*>   2400-RETRO-ELIG      coverage changed after date of service
*>   2500-DUP-CHECK       duplicate claim, with payer exception
*>   2600-PAPER-CLAIM     paper claim handling
*> ================================================================
 IDENTIFICATION DIVISION.
 PROGRAM-ID. CLMEDIT.

 ENVIRONMENT DIVISION.
 INPUT-OUTPUT SECTION.
 FILE-CONTROL.
     SELECT CLAIMS-IN  ASSIGN TO "CLAIMSIN"
         ORGANIZATION IS LINE SEQUENTIAL.
     SELECT CLAIMS-OUT ASSIGN TO "CLAIMSOUT"
         ORGANIZATION IS LINE SEQUENTIAL.

 DATA DIVISION.
 FILE SECTION.
 FD  CLAIMS-IN.
     COPY "CLAIMREC.cpy".
 FD  CLAIMS-OUT.
 01  OUT-REC                     PIC X(300).

 WORKING-STORAGE SECTION.
 01  WS-EOF                      PIC X VALUE "N".
     88  END-OF-CLAIMS           VALUE "Y".
 01  WS-AUTH-COUNT               PIC 9(3) VALUE 0.
 01  WS-DAYS-LATE                PIC S9(7) VALUE 0.
 01  WS-KEY                      PIC X(23).
 01  WS-FOUND                    PIC X VALUE "N".
 01  WS-I                        PIC 9(5) VALUE 0.
 01  WS-SEEN-COUNT               PIC 9(5) VALUE 0.
 01  WS-SEEN-TABLE.
     05  WS-SEEN-KEY OCCURS 5000 TIMES PIC X(23).
 01  WS-COUNTS.
     05  WS-READ                 PIC 9(7) VALUE 0.
     05  WS-ACCEPTED             PIC 9(7) VALUE 0.
     05  WS-REJECTED             PIC 9(7) VALUE 0.
     05  WS-QUEUED               PIC 9(7) VALUE 0.

 PROCEDURE DIVISION.
 0000-MAIN.
     OPEN INPUT CLAIMS-IN
          OUTPUT CLAIMS-OUT
     PERFORM UNTIL END-OF-CLAIMS
         READ CLAIMS-IN
             AT END
                 SET END-OF-CLAIMS TO TRUE
             NOT AT END
                 PERFORM 1000-EDIT-CLAIM
         END-READ
     END-PERFORM
     CLOSE CLAIMS-IN CLAIMS-OUT
     DISPLAY "CLMEDIT READ " WS-READ
             " ACCEPTED " WS-ACCEPTED
             " REJECTED " WS-REJECTED
             " QUEUED " WS-QUEUED
     STOP RUN.

 1000-EDIT-CLAIM.
     ADD 1 TO WS-READ
     MOVE "A" TO CLM-ROUTE
     MOVE SPACES TO CLM-REJECT-CODE
     IF CLM-FORM-TYPE = "P"
         PERFORM 2600-PAPER-CLAIM
     END-IF
     IF CLM-PA-REQUIRED = "Y"
         PERFORM 2100-PA-SCAN
     END-IF
     PERFORM 2200-TIMELY-FILING
     PERFORM 2300-MODIFIER-CHECK
     PERFORM 2400-RETRO-ELIG
     PERFORM 2500-DUP-CHECK THRU 2500-DUP-CHECK-EXIT
     EVALUATE CLM-ROUTE
         WHEN "A" ADD 1 TO WS-ACCEPTED
         WHEN "R" ADD 1 TO WS-REJECTED
         WHEN "Q" ADD 1 TO WS-QUEUED
     END-EVALUATE
     WRITE OUT-REC FROM CLAIM-REC.

*> RULE PA-SCAN
*> Prior authorization. A claim whose procedure needs prior auth must
*> carry an auth reference, and this edit looks for the text "AUTH"
*> anywhere in the notes. CLM-PA-NUM was added to the record in 2009
*> (manual section 5.1 tells clerks to use it) but this edit was never
*> changed to read it, so clerks keep typing "AUTH ..." into the notes.
 2100-PA-SCAN.
     MOVE 0 TO WS-AUTH-COUNT
     INSPECT CLM-NOTES TALLYING WS-AUTH-COUNT FOR ALL "AUTH"
     IF WS-AUTH-COUNT = 0
         MOVE "R" TO CLM-ROUTE
         MOVE "PA01" TO CLM-REJECT-CODE
     END-IF.

*> RULE TF-365
*> Timely filing. Reject a claim filed more than 365 days after the
*> date of service. (Manual section 4.2 still says 180 days.)
 2200-TIMELY-FILING.
     COMPUTE WS-DAYS-LATE =
         FUNCTION INTEGER-OF-DATE (CLM-FILE-DATE)
       - FUNCTION INTEGER-OF-DATE (CLM-DOS)
     IF WS-DAYS-LATE > 365
         MOVE "R" TO CLM-ROUTE
         MOVE "TF01" TO CLM-REJECT-CODE
     END-IF.

*> RULE MOD-25
*> Same-day evaluation/management visit billed with a procedure.
*> Until 2011 a missing modifier 25 rejected the claim. CR-4471 turned
*> it into a warning on the batch log only, so the claim is ACCEPTED.
*> The old reject lines are left commented out below.
 2300-MODIFIER-CHECK.
     IF CLM-EM-SAME-DAY = "Y" AND CLM-MODIFIER NOT = "25"
         DISPLAY "WARN MOD25 MISSING " CLM-ID
*>       MOVE "R" TO CLM-ROUTE
*>       MOVE "MD25" TO CLM-REJECT-CODE
     END-IF.

*> RULE RETRO-ELIG
*> Coverage changed after the date of service. Do not send the claim
*> to the payer; hold it in the clerk queue so eligibility is checked
*> again first. Not described in the manual.
 2400-RETRO-ELIG.
     IF CLM-ROUTE = "A"
        AND CLM-COVERAGE-CHG-DATE NOT = ZEROS
        AND CLM-COVERAGE-CHG-DATE > CLM-DOS
         MOVE "Q" TO CLM-ROUTE
         MOVE "RE01" TO CLM-REJECT-CODE
     END-IF.

*> RULE DUP-CHK
*> Duplicate check on patient + date of service + procedure code.
*> RULE PAYER-TX017
*> Payer TX017 resubmits corrected claims under the same key, so the
*> duplicate edit is skipped for them. Agreed by phone with the payer
*> in 2007; never written down anywhere else.
 2500-DUP-CHECK.
     IF CLM-PAYER-ID = "TX017"
         GO TO 2500-DUP-CHECK-EXIT
     END-IF
     STRING CLM-PATIENT-ID CLM-DOS CLM-PROC-CODE
         DELIMITED BY SIZE INTO WS-KEY
     END-STRING
     MOVE "N" TO WS-FOUND
     PERFORM VARYING WS-I FROM 1 BY 1
             UNTIL WS-I > WS-SEEN-COUNT OR WS-FOUND = "Y"
         IF WS-SEEN-KEY (WS-I) = WS-KEY
             MOVE "Y" TO WS-FOUND
         END-IF
     END-PERFORM
     IF WS-FOUND = "Y"
         MOVE "R" TO CLM-ROUTE
         MOVE "DP01" TO CLM-REJECT-CODE
     ELSE
         IF WS-SEEN-COUNT < 5000
             ADD 1 TO WS-SEEN-COUNT
             MOVE WS-KEY TO WS-SEEN-KEY (WS-SEEN-COUNT)
         END-IF
     END-IF.
 2500-DUP-CHECK-EXIT.
     EXIT.

*> RULE DEAD-PATH
*> Paper claims (form type P) used to go to the OCR batch. Form type P
*> was retired in 2006 (see CLAIMREC.cpy), so this paragraph never runs.
 2600-PAPER-CLAIM.
     MOVE "R" TO CLM-ROUTE
     MOVE "PP01" TO CLM-REJECT-CODE
     DISPLAY "PAPER CLAIM SENT TO OCR BATCH " CLM-ID.
