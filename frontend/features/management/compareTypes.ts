export type CompareKind = "vocabulary" | "kanji";
export type CompareItem = { match_key: string; source_id: string; source_entry_id: number; book_id: number; chapter_id: number | null; chapter_number: number | null; chapter_title: string | null; part: number | string | null; item_order: number; display: string; reading?: string; meaning: string; is_important?: boolean; onyomi?: string[]; kunyomi?: string[]; examples?: { id: number; word: string; reading: string; meaning: string; is_important?: boolean }[] };
export type CompareResult = { kind: CompareKind; book_ids: number[]; items: CompareItem[] };
export type MatchRow = { key: string; label: string; cells: Map<number, CompareItem[]> };
export type CompareViewSettings = { star: boolean; kanjiExamples: boolean; mainWord: boolean; reading: boolean; meaning: boolean; lesson: boolean; mainWordSize: number };
export type ToggleSetting = Exclude<keyof CompareViewSettings, "mainWordSize">;
