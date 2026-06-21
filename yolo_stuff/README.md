# YOLO

## Analyse einzelner Bilder

- Pretrained Model: Detektion von Schutzausrüstung --> Person, Helm, Sicherheitsweste
- Pretrained Model: Gesichtsdetektion
<br> <br>
Kombination der beiden Themen:
Wenn eine Person detektiert wird, wird geschaut, ob diese eine Sicherheitsweste trägt. Außerdem wird versucht, das Gesicht zu detektieren, denn der Helm muss auf dem Kopf getragen werden (BBoxes überlappen sich) und nicht nur in der Hand gehalten werden. Die Person erhält das Label "Safety Equipment OK", wenn die Veste getragen wird und der Helm auf dem Kopf ist.
<br> <br>
Erweitert wird diese Logik um die Situation "Emergency": Unabhängig von der Sicherheitsausrüstung soll eine liegende Person als Notfall erkannt werden. Das wird durch zwei Möglichkeiten erreicht. Die Verbindungslinie der Mittelpunkte der BBoxes Gesicht und Person (Körpermittelpunkt) is ungefähr waagrecht, wenn die Person liegt. Außerdem ist das Seitenverhältnis der BBox einer liegenden Person deutlich anders als einer stehenden Person.
<br> <br>
Leider erkennen die aktuellen Modelle nur das Gesicht und nicht den Kopf im generellen. Eine Person, die von hinten sichtbar ist und einen Helm auf dem Kopf und eine Sicherheitsweste trägt, wird noch nicht richtig erkannt.
<br> <br>

## Kombination der Datensätze
* [Head Detection (CCTV)](https://www.kaggle.com/datasets/hoangxuanviet/head-detection-cctv)
  * train: 556 samples
  * val: 99 samples
  * test: 88 samples
  * Labels:
    * 0: Head

* [construction-ppe dataset](https://docs.ultralytics.com/datasets/detect/construction-ppe)
  * train: 1132 samples
  * val: 143 samples
  * test: 141 samples
  * Labels:
    * 0: helmet
    * 2: vest
    * 6: person

* [construction site safety (css) image dataset roboflow](https://www.kaggle.com/datasets/snehilsanyal/construction-site-safety-image-dataset-roboflow)
  * train: 2605 samples
  * val: 114 samples
  * test: 82 samples
  * Labels:
    * 0: Hardhat
    * 5: Person
    * 7: Safety Vest


Labels der kombinierten Datensätze:
* 0: Head
* 1: helmet, hardhat
* 2: vest, Safety Vest
* 3: person, Person

<br> <br>
Das Training des kombinierten Modells führte aufgrund mangelnder Datenqualität nicht zum Erfolg. Der aus den einzelnen Datensätzen kombinierte Datensatz müsste noch weiter (automatisiert) annotiert werden. Beispiel: Der Datensatz zur Kopf-Erkennung enthält auch die jeweilige Person im Ganzen, die nicht annotiert ist. Das wurde aus Zeitgründen nicht mehr umgesetzt.