// feedback_receiver.gs
// A Google Apps Script Web App that records 👍/👎 clicks from your daily
// email into a Google Sheet. First-party Google - no third-party service.
//
// Setup:
//   1. Create a Google Sheet with header row: timestamp | category | keywords | vote
//   2. Extensions > Apps Script, paste this in, Save.
//   3. Deploy > New deployment > type "Web app", access "Anyone". Copy the URL
//      into FEEDBACK_APPS_SCRIPT_URL.
//   4. File > Share > Publish to web > CSV. Copy that URL into
//      FEEDBACK_SHEET_CSV_URL (this is how the daily script reads votes back).

function doGet(e) {
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
  var p = e.parameter;
  sheet.appendRow([new Date(), p.category || "", p.keywords || "", p.vote || ""]);
  return HtmlService.createHtmlOutput(
    "<p style='font-family:sans-serif'>Thanks - noted! You can close this tab.</p>"
  );
}
