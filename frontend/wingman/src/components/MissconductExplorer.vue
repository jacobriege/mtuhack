<script setup>
import { onMounted, ref, inject, watch} from 'vue'
import Devider from './Devider.vue'
import Filter from './Filter.vue'

const emit = defineEmits(['loadDetails'])

// Emits the selected misconduct item to the parent inspector.
const loadDetails = (misconduct) => {
  currentMisconduct.value = misconduct;
  console.log("Current misconduct set to", misconduct)
  emit('loadDetails', misconduct)
}
const currentMisconduct = ref(null);
const newtotalcount = ref(0)
const missconducts = ref([]) //set via watch to trigger reactivity
const data = inject('data')


const activeFilters = ref({ startTime: "", endTime: "", flagged: false, read: false })

// Onmount run inital fetch
onMounted(async () => {
  await fetchMissconducts(activeFilters.value)
})

// Fetches misconduct records from the date-filter endpoint.
async function fetchMissconducts(filters) {
  const st = filters.startTime == "" ? 0 : Math.floor(new Date(filters.startTime) / 1000)
  const et = filters.endTime == "" ? Math.floor(new Date().getTime() / 1000) : Math.floor(new Date(filters.endTime) / 1000)
    
  const response = await fetch('http://localhost:5000/violations/bydate?startdate=' + st + '&enddate=' + et + (filters.flagged ? '&flagged=true' : '') + ( filters.read ? '&unread=true' : ''))
  
  const datajson = await response.json()
  if (!response.ok) {
    missconducts.value = []
    console.error('Failed to fetch missconducts', datajson);
    return;
  }
  console.log('Fetched missconducts', datajson);
  missconducts.value = sortByTime(datajson)
}

const sortByTime = (arr) => {
  return arr.sort((a, b) => b.timestamp - a.timestamp);
};


// Applies incoming filter values and refreshes the misconduct list.
const onApplyFilters = (filters) => {
  activeFilters.value = filters
  fetchMissconducts(filters)
}

// Builds the filter summary text shown under the list title.
function getFilterText() {
  // helper to prettyfy the filter display. If no filters are active, show "latest". If date filters are active, show the date range. If flagged filter is active, add "flagged" to the display.
  const prettyfydatetime = (datetime,replace="") => {
    if(datetime == "") {
      return replace
    }
    const d = new Date(datetime);
    const f = `${d.getDate()}.${d.getMonth()+1}.${d.getFullYear()} ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`;
    return f
  };

  // Prepend "unread" when unread-only filtering is active.
  const readprefix = activeFilters.value.read ? "unread " : ""
  if(activeFilters.value.flagged == true) {
    return `${readprefix}${prettyfydatetime(activeFilters.value.startTime)} until ${prettyfydatetime(activeFilters.value.endTime,"now")} + flagged`
  } else {
    return `${readprefix}${prettyfydatetime(activeFilters.value.startTime)} until ${prettyfydatetime(activeFilters.value.endTime,"now")}`
  }

}
// Maps backend misconduct types to human-readable labels.
function showtype(misconduct) {
  if(misconduct.type == "no_hardhat") {
    return "Missing Hardhat"
  } else if(misconduct.type == "no_west" || misconduct.type == "no_safety_vest") {
    return "No Safety Vest"
  } else if(misconduct.type == "emergency") {
    return "Emergency lying down"
  } else {
    return misconduct.type
  }
}

// Formats a misconduct timestamp into DD.MM.YYYY.
function prettyDate(misconduct) {
  const d = new Date(misconduct.timestamp*1000);
  console.log(d)
  return `${d.getDate()}.${d.getMonth()+1}.${d.getFullYear()}`;
}

// Formats a misconduct timestamp into HH:MM.
function prettyTime(misconduct) {
  const d = new Date(misconduct.timestamp*1000);
  return `${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`;
}

// Keeps the count title in sync with the loaded misconduct list.
watch(missconducts, (newVal) => {
  newtotalcount.value = newVal.length
})

// Auto-selects the first item whenever the list changes.
watch(missconducts, (newVal) => {
  missconducts.value = newVal
  if(newVal.length > 0) {
    loadDetails(newVal[0])
  } else {
    loadDetails(null)
  }
})

watch(() => data.value.updatecounter, async (newVal) => {
  await fetchMissconducts(activeFilters.value)
})

</script>

<template>
  <div class="missconduct-explorer">
    <div class="topline">
      <div>
        <div class="title">{{ newtotalcount }} Events</div>
        <div class="filterdisplay">
          {{ getFilterText() }}
        </div>
      </div>
      <Filter @applyFilters="onApplyFilters" />
    </div>

      <Devider />

      <transition-group name="fade-slide" tag="div" class="missconducts" appear>
        <div v-if="missconducts.length === 0" class="empty">No new missconducts detected</div>
        <div v-else v-for="missconduct in missconducts" :key="missconduct.violationId" :class="['missconduct', { active: currentMisconduct && currentMisconduct.violationId === missconduct.violationId }]"  @click="loadDetails(missconduct)">
          <div class="type">{{ showtype(missconduct) }}</div>
          <div class="details">
            <div class="time">{{ prettyTime(missconduct) }}</div>
            <div class="date">{{ prettyDate(missconduct) }}</div>
          </div>  
        </div>
      </transition-group>
    </div>
</template>

<style scoped>
.missconduct-explorer {
  display: flex;
  height: min(300px, 40vh);
  flex-direction: column;
}

.filter {
  display: flex;
  padding: 0.3rem;
  place-items: center;
  gap: 0.4rem;
  border-radius: 10px;
  border: 1px solid var(--color-border);
}
.title {
  font-size: 1.2rem;
  font-weight: 500;
  color: var(--color-heading);

}
.missconducts {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  height: min(200px, 35vh);
  overflow-y: auto;
}
.missconduct {
  border-radius: 8px;
  padding: 0.8rem;
  display: flex;
  justify-content: space-between;
  background-color: var(--primary);
  transform: translateY(0);
  opacity: 1;
  transition: transform 220ms ease, opacity 220ms ease, color 220ms ease, background-color 220ms ease;
}

.missconduct.active {
  background-color: var(--secondary);
  outline: 1px solid var(--color-border);
  color: var(--color-background)
}
.fade-slide-enter-from,
.fade-slide-appear-from,
.fade-slide-leave-to {
  opacity: 0;
  transform: translateY(-20px);
}
.fade-slide-enter-active,
.fade-slide-appear-active,
.fade-slide-leave-active {
  transition: transform 220ms ease, opacity 220ms ease;
}
.missconduct:active {
  background-color: var(--primary-hover);
  transform: scale(0.98);
}

.topline {
  padding: 0.5rem;
  display: flex;
  justify-content: space-between;
  gap: 1rem;
}

.filter {
  display: flex;
  place-items: center;
  gap: 0.4rem;
}

.details {
  display: flex;
  gap: 0.8rem;
}

.empty {
  position: absolute;
}

</style>
