# Browser Extension Store Release Checklist

This checklist prepares a customer-facing distribution without claiming that
an official store listing exists. The release owner supplies store account,
publisher, support, and listing details at submission time.

## Before upload

- [ ] Confirm the version in `extension/manifest.json` and the release notes.
- [ ] Replace the publisher placeholder in `docs/STORE_LISTING.md`.
- [ ] Review `docs/PRIVACY.md` and complete the store privacy questionnaire.
- [ ] Capture the required screenshots from the real extension UI.
- [ ] Run `python scripts/validate_extension.py`.
- [ ] Run `python scripts/package_release.py`.
- [ ] Confirm the extension ZIP contains `manifest.json` at its root.
- [ ] Confirm the ZIP contains no `.env`, database, cache, build, or installer files.
- [ ] Record the SHA-256 digest of the uploaded ZIP in the release record.

The repository intentionally does not contain a store URL. Replace these
placeholders only after the publisher's listing is approved:

- Chrome Web Store listing: `<CHROME_WEB_STORE_URL_TO_BE_ASSIGNED>`
- Microsoft Edge Add-ons listing: `<EDGE_ADDONS_URL_TO_BE_ASSIGNED>`

## Upload

1. Open the official publisher dashboard for the target browser.
2. Upload `dist/cps-extension-v<version>.zip`.
3. Paste the reviewed copy from `docs/STORE_LISTING.md`.
4. Complete the permissions and data-use disclosures using `docs/PRIVACY.md`.
5. Add the screenshots and publisher support contact.
6. Submit for review according to the store's current process.

## After publication

- [ ] Record the official listing identifier and URL in the release record.
- [ ] Update this document's publication status and the README only after approval.
- [ ] Verify installation, first-run backend guidance, offline mode, and optional
      provider-key flow from a clean browser profile.
- [ ] Retain the exact uploaded ZIP and validation output for reproducibility.

Until those fields are completed, the project makes no claim that C.P.S. is
published or approved by any official store.
