import numpy as np
from scipy.optimize import linear_sum_assignment


def iou(bb_test, bb_gt):
    xx1 = max(bb_test[0], bb_gt[0])
    yy1 = max(bb_test[1], bb_gt[1])
    xx2 = min(bb_test[2], bb_gt[2])
    yy2 = min(bb_test[3], bb_gt[3])
    w = max(0., xx2 - xx1)
    h = max(0., yy2 - yy1)
    intersection = w * h
    area_test = (bb_test[2]-bb_test[0]) * (bb_test[3]-bb_test[1])
    area_gt   = (bb_gt[2]-bb_gt[0])   * (bb_gt[3]-bb_gt[1])
    union = area_test + area_gt - intersection
    return intersection / union if union > 0 else 0


class KalmanBoxTracker:
    count = 0

    def __init__(self, bbox):
        self.id = KalmanBoxTracker.count
        KalmanBoxTracker.count += 1
        self.bbox = np.array(bbox[:4], dtype=float)
        self.hits = 1
        self.no_losses = 0

    def update(self, bbox):
        self.bbox = np.array(bbox[:4], dtype=float)
        self.hits += 1
        self.no_losses = 0

    def predict(self):
        return self.bbox

    def get_state(self):
        return self.bbox


class Sort:
    def __init__(self, max_age=10, min_hits=2, iou_threshold=0.3):
        self.max_age = max_age
        self.min_hits = min_hits
        self.iou_threshold = iou_threshold
        self.trackers = []
        KalmanBoxTracker.count = 0

    def update(self, dets=np.empty((0, 5))):
        predicted = [t.predict() for t in self.trackers]

        matched, unmatched_dets = self._associate(dets, predicted)

        for t_idx, d_idx in matched:
            self.trackers[t_idx].update(dets[d_idx])

        for d_idx in unmatched_dets:
            self.trackers.append(KalmanBoxTracker(dets[d_idx]))

        results = []
        alive = []
        for t in self.trackers:
            t.no_losses += 1
            if t.no_losses <= self.max_age:
                alive.append(t)
                if t.hits >= self.min_hits:
                    b = t.get_state()
                    results.append([b[0], b[1], b[2], b[3], t.id + 1])

        self.trackers = alive
        return np.array(results) if results else np.empty((0, 5))

    def _associate(self, dets, preds):
        if len(preds) == 0 or len(dets) == 0:
            return [], list(range(len(dets)))

        iou_matrix = np.zeros((len(preds), len(dets)))
        for p, pred in enumerate(preds):
            for d, det in enumerate(dets):
                iou_matrix[p][d] = iou(pred, det[:4])

        row_ind, col_ind = linear_sum_assignment(-iou_matrix)
        matched, unmatched_dets = [], []

        matched_det_indices = set()
        for r, c in zip(row_ind, col_ind):
            if iou_matrix[r][c] >= self.iou_threshold:
                matched.append((r, c))
                matched_det_indices.add(c)

        for d in range(len(dets)):
            if d not in matched_det_indices:
                unmatched_dets.append(d)

        return matched, unmatched_dets
