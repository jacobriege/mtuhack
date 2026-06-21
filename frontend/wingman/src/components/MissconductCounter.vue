<script setup>
import {onMounted,inject ,ref,watch} from 'vue';

const data = inject('data')

watch(data.value.updatecounter, () => {
  // trigger update of the pie chart when the data changes
  fetchCount();
}, { deep: true })




// LOads the Chart.js library and registers the necessary components for creating a pie chart.
import { Chart, PieController, ArcElement, Tooltip, Legend } from 'chart.js'

Chart.register(PieController, ArcElement, Legend, Tooltip);

const canvas = ref(null)
onMounted(async () => {
  await fetchCount();
  new Chart(canvas.value, {
    type: 'pie',
    data: {
      labels: computeLabel(),
      datasets: [
        {
          data: getData(),
          backgroundColor: getColor(),
        }
      ]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
            color: 'var(--color-text)',
            position: 'right',
            labels: {
                boxWidth: 12,
                padding: 12
            }
            }
        }
        }
  })
})

//helper for color of pychart
function getColor() {
    if(noHardhatCount.value === 0 && noWesthatCount.value === 0 && emergencyCount.value === 0) {
        return ['#222222'];
    }
    var ret = [];
    if (noHardhatCount.value > 0) {
        ret.push('#4764e8');
    }
    if (noWesthatCount.value > 0) {
        ret.push('#42b983');
    }
    if (emergencyCount.value > 0) {
        ret.push('#ff6384');
    }
    return ret;
}

//helper for data of pychart
function getData() {
    if(noHardhatCount.value === 0 && noWesthatCount.value === 0 && emergencyCount.value === 0) {
        return [1];
    }
    var ret = [];
    if (noHardhatCount.value > 0) {
        ret.push(noHardhatCount.value);
    }
    if (noWesthatCount.value > 0) {
        ret.push(noWesthatCount.value);
    }
    if (emergencyCount.value > 0) {
        ret.push(emergencyCount.value);
    }
    return ret;
}

//helper for label of pychart
function computeLabel() {
    if (noHardhatCount.value === 0 && noWesthatCount.value === 0 && emergencyCount.value === 0) {
        return ['No missconducts'];
    }
    var ret = [];
    if (noHardhatCount.value > 0) {
        ret.push(`Missing Hardhat: ${noHardhatCount.value}`);
    }
    if (noWesthatCount.value > 0) {
        ret.push(`No Safety Vest: ${noWesthatCount.value}`);
    }
    if (emergencyCount.value > 0) {
        ret.push(`Emergency: ${emergencyCount.value}`);
    }
    return ret;
}

// Variables of miscnduct. Trigger update of the pie chart when they change.
const noHardhatCount = ref(0);
const noWesthatCount = ref(0);
const emergencyCount = ref(0);

// Gets the count of missconducts for the last 7 days from the backend when initally loading the component
const fetchCount = async () => {
  const response = await fetch('http://localhost:5000/violations/count');
  const data = await response.json();
  for (const item of data) {
    if (item.type === 'no_hardhat') {
      noHardhatCount.value = item.count;
    } else if (item.type === 'no_west') {
      noWesthatCount.value = item.count;
    } else if (item.type === 'emergency') {
      emergencyCount.value = item.count;
    }
  }
}

// update on incomming change
watch(() => data.value.updatecounter, async (newVal) => {
  await fetchCount()
})

</script>

<template>
  <div class="missconduct-counter">
    <div class="title">Detection of the last 7 days</div>
    <div class="pie-node">
        <canvas ref="canvas"></canvas>
    </div>
    
  </div>
</template>

<style scoped>

.pie-node {
  margin-top: 1rem;
  width: 100%;
  height: 180px;
}

.title {
  font-size: 1.2rem;
  font-weight: 500;
  color: var(--color-heading);

}


</style>
