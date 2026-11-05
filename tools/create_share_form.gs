/**
 * One-time setup for the Photo Archive "Share a photo" form.
 *
 * Run it while signed in to the Google account OHDS controls, not a personal one.
 * It creates, all inside one Drive folder:
 *   - the form (no file-upload question, so visitors need no Google account)
 *   - a response spreadsheet linked to it
 *   - an email alert to NOTIFY on every new response
 *
 * How to run
 *   1. Go to https://script.google.com and click New project.
 *   2. Replace the sample code with this file. Set NOTIFY below.
 *   3. Choose `setup` in the function menu and click Run. Approve the permissions.
 *   4. Open View > Logs (or Execution log) and copy the three lines it prints:
 *      the folder link, the form link, and the prefilled link template.
 *
 * Run it once. Running again makes a second copy of everything.
 */

// Who gets an email for each new submission. Comma-separated.
const NOTIFY = 'volunteer@example.org';

const FOLDER_NAME = 'Photo Archive Submissions';
const FORM_TITLE  = 'Share a photo with the Oregon Historic District';

function setup() {
  const folder = DriveApp.createFolder(FOLDER_NAME);
  const scans  = folder.createFolder('Scans and originals');   // volunteers file received photos here

  const form = FormApp.create(FORM_TITLE)
    .setDescription(
      'Have a photo of a building or street in the Oregon Historic District? ' +
      'Tell us about it and an OHDS volunteer will follow up to add it to the Photo Archive. ' +
      'Prints are welcome: we can scan them.')
    .setCollectEmail(false)
    .setLimitOneResponsePerUser(false)
    .setAllowResponseEdits(false)
    .setConfirmationMessage(
      'Thank you. An OHDS volunteer will be in touch about your photo.');

  const address = form.addTextItem()
    .setTitle('Address or location')
    .setHelpText('For example "22 Brown St" or "E. Fifth St at Jackson".')
    .setRequired(true);

  form.addTextItem()
    .setTitle('Approximate year taken')
    .setHelpText('A guess is fine, for example "late 1970s".');

  form.addTextItem().setTitle('Who took it (if known)');

  form.addParagraphTextItem()
    .setTitle('What you know about the building or the photo');

  form.addMultipleChoiceItem()
    .setTitle('What kind of photo is it?')
    .setChoiceValues(['A print or slide I can lend for scanning', 'A digital file', 'Not sure'])
    .setRequired(true);

  form.addTextItem()
    .setTitle('Link to the photo (optional)')
    .setHelpText('If it is already online, for example in Google Photos or Dropbox, paste a shared link.');

  form.addTextItem().setTitle('Your name').setRequired(true);

  form.addTextItem()
    .setTitle('Email or phone')
    .setHelpText('So a volunteer can reach you about the photo.')
    .setRequired(true);

  form.addCheckboxItem()
    .setTitle('Permission')
    .setChoiceValues(['I took this photo or have permission to share it, and OHDS may publish it in the Photo Archive.'])
    .setRequired(true);

  // Responses go to a sheet in the same folder.
  const sheet = SpreadsheetApp.create(FORM_TITLE + ' (responses)');
  form.setDestination(FormApp.DestinationType.SPREADSHEET, sheet.getId());

  // Keep everything together.
  DriveApp.getFileById(form.getId()).moveTo(folder);
  DriveApp.getFileById(sheet.getId()).moveTo(folder);

  // Email alert on each submission.
  ScriptApp.newTrigger('notify').forForm(form).onFormSubmit().create();
  PropertiesService.getScriptProperties().setProperties({
    sheetUrl: sheet.getUrl(),
    scansUrl: scans.getUrl(),
  });

  // The archive fills in the address for the building being viewed.
  const prefilled = form.createResponse()
    .withItemResponse(address.createResponse('ADDRESS_HERE'))
    .toPrefilledUrl();

  Logger.log('Folder:    ' + folder.getUrl());
  Logger.log('Form:      ' + form.getPublishedUrl());
  Logger.log('Prefilled: ' + prefilled);
}

function notify(e) {
  const props = PropertiesService.getScriptProperties();
  const lines = e.response.getItemResponses()
    .map(r => r.getItem().getTitle() + ': ' + r.getResponse())
    .join('\n');
  MailApp.sendEmail({
    to: NOTIFY,
    subject: 'New Photo Archive submission',
    body: lines +
      '\n\nAll responses: ' + props.getProperty('sheetUrl') +
      '\nFile received scans in: ' + props.getProperty('scansUrl'),
  });
}
