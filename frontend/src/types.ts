export interface ScoreBucket {
  bucket: string;
  count: number;
}

export interface PassRate {
  task: string;
  avg_score: number;
  attempts: number;
}

export interface TimelinePoint {
  date: string;
  submissions: number;
}

export interface GroupPerformance {
  group: string;
  avg_score: number;
  students: number;
}