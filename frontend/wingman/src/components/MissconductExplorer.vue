<script setup>
import { onMounted, ref , watch} from 'vue'
import Devider from './Devider.vue'
import Filter from './Filter.vue'

const emit = defineEmits(['loadDetails'])

// Emits the selected misconduct item to the parent inspector.
const loadDetails = (misconduct) => {
  emit('loadDetails', misconduct)
}
const newtotalcount = ref(0)
const missconducts = ref([])



const activeFilters = ref({ startTime: "", endTime: "", flagged: false })

onMounted(async () => {
  await fetchMissconducts(activeFilters.value)
})

// Fetches misconduct records using either unread or date-range endpoints.
async function fetchMissconducts(filters) {
  var response;
  if(filters.startTime == "" && filters.endTime == "" && filters.flagged == false) {
    response = await fetch('http://localhost:8000/violations/unread')
  } else {
    const st = filters.startTime == "" ? 0 : Math.floor(new Date(filters.startTime) / 1000)
    const et = filters.endTime == "" ? Math.floor(new Date().getTime() / 1000) : Math.floor(new Date(filters.endTime) / 1000)
    
    response = await fetch('http://localhost:8000/violations/bydate?startdate=' + st + '&enddate=' + et + (filters.flagged ? '&flagged=true' : ''))
  }
  const data = await response.json()
  if (!response.ok) {
    missconducts.value = []
    console.error('Failed to fetch missconducts', data);
    return;
  }
  console.log(data)
  missconducts.value = data
}




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
  if(activeFilters.value.startTime != "" || activeFilters.value.endTime != "") {
    if(activeFilters.value.flagged == true) {
      return `${prettyfydatetime(activeFilters.value.startTime)} - ${prettyfydatetime(activeFilters.value.endTime,replace="now")} • flagged`
    } else {
      return `${prettyfydatetime(activeFilters.value.startTime)} - ${prettyfydatetime(activeFilters.value.endTime)}`
    }
  } else {
    return "latest"
  }
}

// Maps backend misconduct types to human-readable labels.
function showtype(misconduct) {
  if(misconduct.type == "no_hardhat") {
    return "Missing Hardhat"
  } else if(misconduct.type == "no_safety_vest") {
    return "No Safety Vest"
  } else if(misconduct.type == "emergency") {
    return "Emergency lying down"
  } else {
    return misconduct.type
  }
}

// Formats a misconduct timestamp into DD.MM.YYYY.
function prettyDate(misconduct) {
  const d = new Date(misconduct.timestamp);
  console.log(d)
  return `${d.getDate()}.${d.getMonth()+1}.${d.getFullYear()}`;
}

// Formats a misconduct timestamp into HH:MM.
function prettyTime(misconduct) {
  const d = new Date(misconduct.timestamp);
  return `${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`;
}

// Keeps the count title in sync with the loaded misconduct list.
watch(missconducts, (newVal) => {
  newtotalcount.value = newVal.length
})

// Auto-selects the first item whenever the list changes.
watch(missconducts, (newVal) => {
  if(newVal.length > 0) {
    loadDetails(newVal[0])
  } else {
    loadDetails(null)
  }
})

</script>

<template>
  <div class="missconduct-explorer">
    <div class="topline">
      <div>
        <div class="title">{{ newtotalcount }} Missconducts</div>
        <div class="filterdisplay">
          {{ getFilterText() }}
        </div>
      </div>
      <Filter @applyFilters="onApplyFilters" />
    </div>

      <Devider />

      <transition-group name="fade-slide" tag="div" class="missconducts" appear>
        <div v-if="missconducts.length === 0" class="empty">No new missconducts detected</div>
        <div v-else v-for="missconduct in missconducts" :key="missconduct.id" class="missconduct" @click="loadDetails(missconduct)">
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
  transition: transform 220ms ease, opacity 220ms ease;
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
  border: 1px solid var(--color-border);
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
