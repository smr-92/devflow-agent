export interface Developer {
  id: string;
  rank: number;
  username: string;
  total_points: number;
  mr_count: number;
  streak_eligible_count: number;
  last_scored_at: string;
}

export interface Dimension {
  score: number;
  weighted: number;
  rationale: string;
}

// Agent sometimes saves flat numbers, sometimes full Dimension objects
export type DimensionValue = Dimension | number;

export interface Score {
  id: string;
  project_id: string;
  mr_iid: number;
  title: string;
  author: string;
  total_score: number;
  complexity: 'small' | 'medium' | 'large';
  complexity_multiplier: number;
  points: number;
  streak_eligible: boolean;
  scored_at: string;
  dimensions: {
    description_quality: DimensionValue;
    code_clarity: DimensionValue;
    test_coverage_signal: DimensionValue;
    pr_size_appropriate: DimensionValue;
    review_responsiveness: DimensionValue;
    iteration_quality: DimensionValue;
  };
}
