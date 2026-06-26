# Firebase CLI

Manage Firebase projects, hosting, functions, and Firestore from terminal.

## Project Setup
```bash
npm install -g firebase-tools
firebase login                           # Authenticate
firebase init                            # Init project (hosting, functions, firestore)
firebase projects:list                   # List projects
firebase use --add                       # Set active project
```

## Hosting
```bash
firebase deploy --only hosting           # Deploy static site
firebase hosting:channel:deploy preview  # Deploy to preview channel
firebase serve                           # Local emulator
```

## Firestore
```bash
# Read/write via Firebase Admin SDK
python -c "
import firebase_admin
from firebase_admin import credentials, firestore
cred = credentials.ApplicationDefault()
firebase_admin.initialize_app(cred)
db = firestore.client()
docs = db.collection('users').limit(10).stream()
for doc in docs:
    print(f'{doc.id}: {doc.to_dict()}')
"
```

## Functions
```bash
firebase deploy --only functions         # Deploy cloud functions
firebase functions:shell                 # Local test shell
firebase functions:log                   # View logs
```

## Emulator Suite
```bash
firebase emulators:start                 # Full local emulator
firebase emulators:start --only firestore,auth,functions
```
