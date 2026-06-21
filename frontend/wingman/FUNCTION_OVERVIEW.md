# Wingman Function Overview

Brief predicted behavior of main frontend functions in `src/components`.

## Inspector component (`MissconductInspector.vue`)

- `loadDetails(misconduct)`  
  Stores the selected misconduct object and image URL for the details viewer.

## Explorer component (`MissconductExplorer.vue`)

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

## Details viewer component (`MissconductDetailsViewer.vue`)

- `clearImage()`  
  Revokes old object URLs and clears image state.
- `loadImage(id)`  
  Fetches image data from the selected URL and updates display status.

## Counter component (`MissconductCounter.vue`)

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

## Components without script functions

- `Container1.vue` — layout container wrapper using slot content.
- `button1.vue` — stylized button-like slot wrapper.
- `Devider.vue` — horizontal divider UI element.
- `VerticalDevider.vue` — vertical divider UI element.
- `MisconductTimeline.vue` — currently empty placeholder component.
