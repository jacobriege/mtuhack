<script setup>
import {onMounted,ref} from 'vue';

import { Chart, PieController, ArcElement, Tooltip, Legend } from 'chart.js'

Chart.register(PieController, ArcElement, Legend, Tooltip);

const canvas = ref(null)
onMounted(() => {
  new Chart(canvas.value, {
    type: 'pie',
    data: {
      labels: ['Test1', 'test2', 'C'],
      datasets: [
        {
          data: [30, 50, 20],
          backgroundColor: ['#42b983', '#ff6384', '#36a2eb']
        }
      ]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
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
.missconduct-explorer {
  display: flex;
  flex-direction: column;
}
.pie-node {
  margin-top: 1rem;
  width: 100%;
  height: 180px;
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
.missconducts-types {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.missconduct {
  border-radius: 8px;
  padding: 0.8rem;
  display: flex;
  justify-content: space-between;
  background-color: var(--primary);
}
.missconduct:active {
  background-color: var(--primary-hover);
  border: 1px solid var(--color-border);
}

.topline {
  padding: 0.5rem;
  padding-bottom: 1rem;
  display: flex;
  justify-content: space-between;
  gap: 1rem;
}

.filter {
  display: flex;
  place-items: center;
  gap: 0.4rem;
}


</style>
