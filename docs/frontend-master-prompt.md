Design the frontend for "Privacy Gateway": a website that lets people use AI on documents that contain Indian personal data, without the AI ever seeing the real personal data.

THE WORKFLOW (what happens every time a user submits something)

Step 1 – Give input
The user either pastes text or uploads a document (PDF or image). A PDF can have up to 50 pages.
They also choose:
- what they want done (for example "Summarise this document")
- a purpose: Support summary, Eligibility review or Document classification

Step 2 – Read the document
If a file was uploaded, its text is read from the pages. The user sees the file name and the number of pages.

Step 3 – Find personal data
The system finds private details in the text: names, addresses, Aadhaar numbers, PAN numbers, GST numbers, Voter IDs, passport numbers, phone numbers and emails. It understands English and Hinglish.

Step 4 – Check the IDs are correct
Each ID number is checked to see whether it is a valid number.
- All correct: continue.
- Any wrong: STOP. Nothing is sent to the AI. The user sees each wrong ID, the reason it's wrong (for example "This Aadhaar number has 11 digits, it needs 12"), and a box to correct it. They then submit again.

Step 5 – Hide the personal data
Every private value is replaced with a tag, for example "Rahul Sharma" becomes <PERSON_1> and the Aadhaar number becomes <AADHAAR_1>. The same value always gets the same tag.

Step 6 – Safety checks
Before anything leaves, three checks run:
- Leak check: is any real value still visible? If yes: STOP ("Blocked: real data would have leaked").
- Trick check: is the document trying to give the AI hidden instructions? If yes: STOP ("Blocked: suspicious instructions found").
- Too many requests: is the user sending too fast? If yes: ask them to wait, with a countdown.

Step 7 – Ask the AI
Only the hidden version (with tags) is sent to the AI. The AI answers using the tags.

Step 8 – Put the real data back
The tags in the AI's answer are replaced with the real values, and the user gets the final answer. The system also reports:
- how many tags were restored
- whether the AI lost any tags
- whether the AI made up any tags that never existed

Step 9 – Keep a record
Every request is saved in a history log. The log never contains the real personal data, only counts, tags and the result.

POSSIBLE RESULTS (each needs its own clear look)
- Success: protected and answered.
- Warning: answered, but the AI lost or invented some tags.
- Fix needed: some IDs are wrong; the user must correct them.
- Blocked (leak): stopped, because real data would have leaked.
- Blocked (trick): stopped, because the document tried to give the AI instructions.
- Slow down: too many requests; try again after a short wait.
- AI unavailable: the AI could not be reached; nothing was lost.

WHAT THE USER SHOULD SEE
- A progress bar of the steps above that lights up as each one finishes, and shows clearly where it stopped if it stopped.
- Three views side by side:
  - "Your original", with private values highlighted
  - "What the AI saw", with tags instead of real values
  - "Final answer", with real values back
- A list of every private item found: its type, the value (hidden until clicked), and its tag.
- A correction view for wrong IDs.
- A history page with counts for each result type and a list of past requests, showing no real data.
- A "Security tests" page where visitors can try attack examples and see each one being blocked.
- Ready-made example buttons that fill in sample text:
  - Hinglish
  - Wrong IDs
  - Loan application
  - KYC
  - Support ticket
  - No personal data
  - Trick attempt

EXAMPLE
User input:  "Mera naam Rahul Sharma hai. PAN BNZPM2501F, Aadhaar 4991 1866 5246. Rahul Sharma ka mobile 98765 43210 hai."
AI sees:     "Mera naam <PERSON_1> hai. PAN <PAN_1>, Aadhaar <AADHAAR_1>. <PERSON_1> ka mobile <PHONE_1> hai."
Final answer: the AI's reply with Rahul Sharma, the PAN, the Aadhaar and the phone number put back in.
Wrong ID example: "Aadhaar: 1234 5678 901" → "This Aadhaar number has 11 digits. Please check it and enter it again."
