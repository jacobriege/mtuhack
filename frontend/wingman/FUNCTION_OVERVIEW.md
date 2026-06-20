# Wingman Function Overview

Brief predicted behavior of main frontend functions in `src/components`.

## `MissconductInspector.vue`

- `loadDetails(misconduct)`  
  Stores the selected misconduct object and image URL for the details viewer.

## `MissconductExplorer.vue`

- `loadDetails(misconduct)`  
  Emits selected misconduct to the parent.
- `fetchMissconducts(filters)`  
  Loads misconducts from unread or date-filtered backend endpoints.
- `onApplyFilters(filters)`  
  Saves active filter values and refreshes the list.
- `getFilterText()`  
  Generates a compact filter summary label for the UI.
- `showtype(misconduct)`  
  Converts backend misconduct type keys to display labels.
- `prettyDate(misconduct)`  
  Formats misconduct timestamp to date text.
- `prettyTime(misconduct)`  
  Formats misconduct timestamp to time text.

## `Filter.vue`

- `openPopup()`  
  Opens the filter dialog.
- `closePopup()`  
  Closes the filter dialog.
- `applyFilters()`  
  Emits currently selected filter values.
- `resetFilters()`  
  Clears all filter inputs to defaults.

## `MissconductDetailsViewer.vue`

- `clearImage()`  
  Revokes old object URLs and clears image state.
- `loadImage(id)`  
  Fetches image data from the selected URL and updates display status.

## `MissconductCounter.vue`

- `getColor()`  
  Selects pie chart colors for available categories.
- `getData()`  
  Produces numeric chart data from misconduct counts.
- `computeLabel()`  
  Builds pie chart labels with category count text.
- `initalCountFetch()`  
  Fetches backend misconduct counts and stores them in reactive values.

## `Flagbutton.vue`

- `flagMisconduct()`  
  Placeholder action that currently shows an alert.
