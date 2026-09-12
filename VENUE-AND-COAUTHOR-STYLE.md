# Venue and Co-author Style Evidence

Status: IN PROGRESS. Written incrementally; each section is filled as evidence is gathered and measured directly from source. Where a source could not be fetched, this is stated rather than guessed.

Target venue: IEEE BigData 2026, Intelligent Data Mining special session.

---

## PART 1: VENUE CONVENTIONS

### Note on sourcing

The IEEE BigData 2024 program schedule (`https://www3.cs.stonybrook.edu/~ieeebigdata2024/BD2024-Program-Schedule.pdf`, 55 pages, fetched and read in full) lists the "Special Session: Intelligent Data Mining" only as a room/time/chair entry (Sunday Dec 15, 9:00-17:00, Sequoia room, chair Uraz Yavanoglu, the session's 11th/9th iteration depending on source) but does NOT publish a paper title list for that session anywhere in the document, unlike the main-conference D1S/D2S/D3S tracks and the Industry & Government (I&G) sessions, which are listed paper-by-paper with authors. The IEEE BigData 2023 special-session page (`bigdataieee.org/BigData2023/SpecialSession.html`) likewise gives only the call for papers, no accepted-paper list. I could not locate a published Intelligent Data Mining session paper list for 2022-2025 within the search budget of this task.

Per the task's own fallback instruction, the four sampled papers below are therefore **IEEE BigData 2024 main-conference proceedings papers, explicitly labelled as main track (not Intelligent Data Mining special session)**, chosen because their arXiv preprints are full-text readable. All four appear in the IEEE BigData 2024 Program Schedule's main paper-session tables (confirmed against the schedule PDF).

### Paper 1: BanglaDialecto

- Samin, Ahad, Medha, Rahman, Amin, Mohammed, Rahman. "BanglaDialecto: An End-to-End AI-Powered Regional Speech Standardization." arXiv:2411.10879. IEEE BigData 2024, session D2S1 (Foundation Models and Analytics), paper BigD889.
- Year: 2024.
- Page count: 10 pages (2-column IEEE format), including references.
- Abstract: approximately 275 words by manual count of the arXiv/IEEE abstract text. Contains numerals: yes -- "55 distinct dialects," "160 million people," "CER of 0.8%," "WER of 1.5%," "BLEU score of 41.6%."
- Introduction: 6 paragraphs (unlabelled prose paragraphs; no subheadings inside the introduction other than inline lettered tags described next).
- Challenges enumerated: yes, but not as a displayed list or table -- as inline lettered parenthetical tags embedded in running prose, e.g. Section III: "we focused on addressing two key challenges. (a) Managing large-scale speech signals: ... (b) Improving performance in dialect translation: ...". The same "(a) / (b)" inline-bold-lead-in device recurs in the introduction's related-work framing and in the model-architecture subsection. Contributions are typeset the same way: "Our contributions comprise (1) ... (2) ... (3) ..." inline, not as a bulleted list.
- Tables: 5 (dataset statistics, ASR/MT comparison to prior work, pretrained-vs-fine-tuned results, end-to-end generation examples, English gloss of those examples).
- Figures: 4 (system pipeline diagram, architecture diagram, a bar chart of participant regions, a two-panel ablation chart).
- Results organized around research questions: no. Results section ("IV. Experiment," subsection "B. Results and Analysis") is organized by task/component with bolded run-in headers ("Bangla Dialect Speech Recognition:", "Performance Analysis of Translation Models:"), not "RQ1/RQ2" framing.
- Limitations: a short dedicated "Limitations:" paragraph (3 sentences) sits inside the Discussion subsection (IV.D), before the Conclusion section -- not inside the Conclusion itself.
- Conclusion: one paragraph of about 13 sentences (~190 words) restating the pipeline and results, followed by a separate short "Future works:" paragraph (3 sentences). An "Ethics Statement" section follows the conclusion, before references.

### Paper 2: DP-TabICL

- Carey, Bhaila, Edemacu, Wu. "DP-TabICL: In-Context Learning with Differentially Private Tabular Data." arXiv:2403.05681. IEEE BigData 2024, session D1S7 (Data Ecosystem), paper BigD330.
- Year: 2024 (arXiv posted March 2024; IEEE BigData 2024 main track per program schedule).
- Page count: 10 pages (2-column IEEE format), including references, ethics statement, reproducibility statement, acknowledgements.
- Abstract: 220 words by manual count. Contains numerals: no -- all quantities are spelled out ("two private ICL frameworks," "eight real-world tabular datasets"); no digit numerals appear anywhere in the abstract. This is a direct contrast with BanglaDialecto's abstract, which uses digit numerals throughout.
- Introduction: 7 paragraphs: (1) LLM/ICL background, (2) tabular-data-as-ICL background, (3) privacy risk motivation, (4) prior DP mitigations and their gap, (5) this-work framing (the longest paragraph, includes both named methods), (6) contributions, (7) one-sentence-per-section roadmap ("The remainder of the work is as follows...").
- Challenges enumerated: not via lettered/numbered inline tags (contrast with BanglaDialecto) -- discussed in ordinary prose sentences.
- Contributions typeset as a genuine bulleted list (three "&#8226;" bullets), not inline parenthetical numerals.
- Tables: 4 (notation table, LDP-TabICL results, GDP-TabICL results, paired-t-test p-values).
- Figures: 2 (method overview diagram; two-panel ablation accuracy plot).
- Results organized around research questions: no. Organized by method-name subsections ("A. LDP-TabICL," "B. GDP-TabICL," "C. LDP-TabICL vs. GDP-TabICL," "4) Llama-2-13B vs. Llama-2-7B") -- comparison-framed subsection headers, not "RQ1/RQ2" labels.
- Limitations: no dedicated "Limitations" heading anywhere in the paper. A methodological caveat appears as a footnote ("This assumption may not hold in all settings...") but there is no section-level limitations discussion.
- Conclusion: one paragraph, about 8 sentences (~150 words), ending with a future-work sentence folded into the same paragraph (no separate "Future Work" heading, unlike BanglaDialecto). Followed by separate "Ethics Statement," "Reproducibility," and "Acknowledgements" sections before references.

### Paper 3: Beyond Human Vision

- Verma, Van, Wu. "Beyond Human Vision: The Role of Large Vision Language Models in Microscope Image Analysis." arXiv:2405.00876. IEEE BigData 2024, session D2S1 (Foundation Models and Analytics), paper BigD507, listed as "Short" in the program schedule.
- Year: 2024.
- Page count: 15 pages (2-column IEEE format) -- notably long for a paper the program schedule classifies as "Short" (11-minute talk slot); the length comes mostly from figure-heavy qualitative VQA transcripts (Figs. 10-13 reproduce full model dialogues).
- Abstract: 207 words by manual count. Contains numerals: no digit numerals anywhere (all quantities named, not counted, in the abstract) -- same pattern as DP-TabICL, contrasting with BanglaDialecto.
- Introduction: 4 paragraphs only (shortest of the four sampled papers): (1) motivation/domain framing, (2) capsule descriptions of each of the four models under study (ChatGPT-4, Gemini, LLaVA, SAM), (3) this-work framing naming the four tasks studied, (4) a roadmap paragraph describing the rest of the paper section by section.
- No separate "contributions" list of any kind -- neither bulleted nor inline-numbered. The four tasks (classification, segmentation, counting, VQA) are named in italics inline in paragraph 3 and this substitutes for a contributions list.
- Challenges enumerated: no lettered/numbered/bulleted challenge list anywhere in the paper.
- Tables: 2 (NFFA dataset class breakdown; SAM-standard vs. SAM-custom parameters).
- Figures: 13 (task/model/dataset overview; sample images; a worked qualitative example; confusion matrices; dice-score scatterplots; difference-image panels; good/bad segmentation examples; predicted-vs-actual count scatterplots x2; four VQA transcript figures).
- Results organized around research questions: no. "VI. Results and Discussion" is organized by the same four task names as the introduction and methods sections (A. Classification, B. Segmentation, C. Counting, D. Visual Question Answering), not "RQ1/RQ2" framing.
- Limitations: no dedicated "Limitations" heading anywhere. The closest analogue is the conclusion's closing sentence about impurities/defects/artefact diversity "challenging the models."
- Conclusion: Section VII "Conclusions," a single paragraph of about 13 sentences (~280 words, the longest conclusion of the four sampled papers), organized task-by-task (classification, then segmentation, then counting, then VQA) before a closing summary sentence. No separate future-work paragraph, no ethics statement -- goes straight from conclusion to "Acknowledgements" to references.

### Paper 4: Targeting Negative Flips

- Benkert, Prabhushankar, AlRegib. "Targeting Negative Flips in Active Learning using Validation Sets." arXiv:2411.10896. IEEE BigData 2024, session D1S12 (Deep Learning II), paper BigD668. Runner-up, Best Paper Award. Date of acceptance per the arXiv cover sheet: 26 October 2024.
- Year: 2024.
- Page count: 10 pages of paper content (2-column IEEE format; the arXiv PDF carries an extra unnumbered cover/citation sheet before page 1, not counted here).
- Abstract: 247 words by manual count. Contains numerals: no digit numerals ("two ways," not "2 ways"); consistent with DP-TabICL and Beyond Human Vision.
- Introduction: 5 paragraphs: (1) software-regression/active-learning framing, (2) brief note on deployable active learning applications, (3) definition of negative flips and the paper's key contradiction-of-assumption claim, (4) this-work framing (validation-set method, RoSE, with forward references to figures/sections rather than a separate roadmap paragraph), (5) contributions.
- Contributions typeset as a displayed, numbered list using the IEEE "1) / 2) / 3)" convention (each on its own line) -- a third distinct contributions-typesetting convention among the four papers (cf. BanglaDialecto's inline "(1)(2)(3)" and DP-TabICL's bulleted list).
- Sub-observations/challenges: Section IV uses italicized run-in subsubsection headers typeset as "a) Class Complexity:" and "b) Class Imbalance:" -- the same lettered-parenthesis device seen in BanglaDialecto, but here used as formal subsubsection headings rather than inline within a sentence.
- Tables: 2 (percentage of rounds RoSE outperforms baseline; accuracy/NFR at selected rounds on CINIC10).
- Figures: 9 (method overview + CINIC10 curves; CIFAR10/100 accuracy-NFR curves; class-complexity curves; class-imbalance curves; restricted-subset sampling curves; three-dataset accuracy curves; three-dataset NFR curves; Convmixer learning curves; 2D spiral-dataset negative-flip visualization).
- Results organized around research questions: **yes** -- the only one of the four sampled papers to do so explicitly. Section VI, "Experiments," opens: "In this section, we provide experimental results to answer the following questions: 1) how well does RoSE perform under several datasets with different types of complexities?; 2) does RoSE perform well with a wide variety of acquisition functions?; and 3) does performance enhancement via RoSE manifest as a net-improvement when considering both regression and overall error rate?" -- three numbered questions, inline in prose (not displayed as a list), then answered in the same order across the section's subsections.
- Limitations: no dedicated "Limitations" heading. A limitations-like admission is folded into the final two sentences of the Conclusion ("While the empirical performance is impressive investigating the reason still requires significant research effort... The observation is compelling but still requires theoretical justification.").
- Conclusion: Section VIII, one paragraph, 7 sentences (~140 words), ending on a future-research sentence folded into the same paragraph. No separate future-work heading, no ethics statement, no reproducibility statement in the paper body (a GitHub code link is given only on the arXiv cover sheet, not in an in-text "Reproducibility" section as DP-TabICL has).

### Shared venue conventions across the four sampled papers

All four are 2024 IEEE BigData main-track papers (the Intelligent Data Mining special session's own paper list could not be located; see the sourcing note above). Measured commonalities:

| Attribute | BanglaDialecto | DP-TabICL | Beyond Human Vision | Negative Flips |
|---|---|---|---|---|
| Pages | 10 | 10 | 15 (short-paper slot) | 10 |
| Abstract words | ~275 | ~220 | ~207 | ~247 |
| Abstract has digit numerals | yes | no | no | no |
| Intro paragraphs | 6 | 7 | 4 | 5 |
| Contributions typesetting | inline "(1)(2)(3)" | bulleted list | none (no list at all) | displayed "1)/2)/3)" list |
| Challenges/sub-points typeset as lettered tags | yes, inline "(a)(b)" | no | no | yes, as subsubsection headers "a)/b)" |
| Tables | 5 | 4 | 2 | 2 |
| Figures | 4 | 2 | 13 | 9 |
| Results organized around RQs | no | no | no | yes (only one) |
| Dedicated Limitations heading | no (folded into Discussion) | no | no | no |
| Conclusion length | ~190 words + separate Future Work para | ~150 words, one para | ~280 words, one para | ~140 words, one para |
| Ethics/Reproducibility statements | Ethics Statement only | Ethics + Reproducibility + Acknowledgements | Acknowledgements only | none (code link on arXiv cover sheet only) |

Conventions that hold across all four, stated with the counts behind them:

1. **Two-column IEEE format, 10 pages typical for a Regular paper** (three of four papers are exactly 10 pages; the fourth, nominally a "Short" paper by the program schedule's own classification, ran to 15 pages on the strength of figure-heavy qualitative transcripts -- so the page count is a norm, not a hard cap enforced at the venue level within this sample).
2. **No "Limitations" section as a matter of course.** Zero of four papers carry a heading literally named "Limitations" as a top-level or Conclusion-adjacent section; where a limitations-like admission appears at all (BanglaDialecto, Negative Flips), it is folded into Discussion or Conclusion prose, not flagged.
3. **Results sections are organized by task/method name, not by research question, in 3 of 4 papers.** Only "Targeting Negative Flips" frames its experiments section around explicit numbered questions; the other three use task-name or method-name subsection headers (e.g., "A. Classification," "B. Segmentation").
4. **A short, single-paragraph Conclusion (7-13 sentences, roughly 140-280 words) is standard**; none of the four uses multiple conclusion subsections, and only one (BanglaDialecto) breaks out a separate "Future Works" paragraph.
5. **Enumeration devices are heterogeneous but always present in some form for contributions or sub-points**, except in "Beyond Human Vision," which has neither a contributions list nor lettered sub-points anywhere -- the only one of the four to omit enumeration entirely. Where enumeration appears, IEEE's lettered/numbered run-in convention -- "(a)/(b)," "a)/b)," "1)/2)/3)" inline, or a bulleted list -- is used, never a boxed callout or a separately titled "Challenges" section.
6. **Abstracts run roughly 200-280 words** and typically end on a results/impact sentence, not a hedge; three of four contain zero digit numerals even when reporting quantitative results (they name counts and metrics in prose, e.g., "eight real-world tabular datasets," rather than writing "8").
7. **No paper in the sample organizes its introduction with a formally numbered "Challenges" list as a first-class heading** (contrast with Part 2 below, where the co-authors' own papers do exactly this).

Because the Intelligent Data Mining special-session paper list itself could not be confirmed (see sourcing note), these conventions should be read as "IEEE BigData 2024 main-conference practice," not verified as special-session-specific practice. Given that the special session uses the same IEEE two-column template and the same paper-length rules published by the conference (confirmed via the BigData2023 special-session call-for-papers page, which states "2-column IEEE format"), the main-track conventions above are very likely to transfer, but this is an inference, not a direct measurement of Intelligent Data Mining session papers.

---

## PART 2: CO-AUTHOR STYLE

### Note on already-measured sources being reused here

Two papers by the Wang/Zhang co-author pair were already read in full and measured, for a different purpose, in `C:/Users/rohit/Documents/Peer reviews/my review skills/SKILL.md` (the `paper-review-lessons` skill). Per this task's own instruction to cite FairGEM rather than redo it, and because the ICDM 2023 paper in the same file was likewise read directly (not assumed from genre) and is cross-attributed to a named co-author review, both are cited below rather than re-read from scratch:

- **FairGEM**: Wang, Yin, Zhang, "A Unified Framework for Fair Graph Generation: Theoretical Guarantees and Empirical Advances," 39th Conference on Neural Information Processing Systems (NeurIPS 2025).
- **ICDM 2023 exemplar**: Wang, Narasimhan, Yao, Zhang, "Mitigating Multisource Biases in Graph Neural Networks via Real Counterfactual Samples," IEEE ICDM 2023, DOI 10.1109/ICDM58522.2023.00073.

Both list a "Wang" and a "Zhang" as co-authors, consistent with Zichong Wang and Wenbin Zhang as the project's co-author reviewers named in the project's own CLAUDE.md.

### Profile identification

Measured directly from each Google Scholar profile page (name, affiliation, and top-cited papers as returned by Scholar):

| URL | Name | Affiliation |
|---|---|---|
| `citations?user=M802p54AAAAJ` | **Wenbin Zhang** | Florida International University |
| `citations?user=NgxMqeEAAAAJ` | **Zichong Wang** | Florida International University |
| `citations?user=1nVpMXgAAAAJ` | **Zhipeng Yin** | Florida International University |

Two of the three are confirmed as Zichong Wang and Wenbin Zhang, as expected. The third is **not** one of the two named co-authors of this project -- it is **Zhipeng Yin**, a Florida International University collaborator who co-authors repeatedly with both Wang and Zhang on fairness-in-AI papers (e.g., "FairAIED," "Fg-smote," "Graph fairness via authentic counterfactuals"). This is very likely the same "Zhipeng" credited in `C:/Users/rohit/Documents/Peer reviews/my review skills/SKILL.md` as "a second reviewer, Zhipeng, on a fairness-in-LLM-agents survey" -- i.e., a third recurring member of the same co-author circle, not an unrelated stranger, but distinct from the two named project co-authors. Flagging this rather than assuming Yin is a stand-in for Zhang or Wang.

Given this, one additional paper was read in full below with Zhipeng Yin as first author, to sample the third profile directly rather than only inferring his style from being a co-author on Wang/Zhang papers.

### Paper read in full: Digital Forensics in the Age of Large Language Models

- Yin, Wang, Xu, Zhuang, Mozumder, Smith, Zhang. arXiv:2504.02963. A survey, not a method paper -- all three profile-holders are co-authors (Zhipeng Yin first author, Zichong Wang second, Wenbin Zhang last/corresponding-adjacent). 22 pages including 116 references, 2-column format.
- Abstract: 218 words by manual count, 9 sentences, zero digit numerals -- same "spelled out, not digited" convention observed for 3 of 4 venue-sample papers in Part 1. Opens with a broad-impact sentence ("Digital forensics plays a pivotal role in modern investigative processes...") with no citation, exactly the ICDM-checklist "broad impact first, no citations needed" order recorded elsewhere in the review-lessons file. Closes not on an artefact/deliverable list but on a forward-looking need statement: "highlighting the need for effective use of LLMs for transparency, accountability, and robust standardization in the forensic process" -- ends on an idea/consequence, not on "we release X."
- Introduction: 6 paragraphs, structured as motivating case narrative rather than gap-then-remedy: (1) historical high-stakes cases (Sony Pictures hack, DNC leak, Silk Road, Enron, child exploitation), (2) general limitations of manual forensic methods, (3) a second wave of recent, more granular cases tied to a figure (2024 Trump assassination attempt, 2020 Twitter hack, 2019 Pensacola shooting), (4) LLMs introduced as the solution direction, (5) elaboration of LLM capabilities against the limitations named in paragraph 2, (6) a transition paragraph ending in a bolded run-in heading, "**Paper Structure.**", that walks through Sections 2-5 by number.
- No contributions list of any kind (no bullets, no inline or displayed numerals) and no separate "challenges" paragraph inside the introduction -- both are absent from this survey's introduction, unlike FairGEM and the ICDM 2023 exemplar (both method papers) already on record in the review-lessons file. Challenges are instead handled as an entire dedicated body section (see below), not as an introduction paragraph.
- Enumeration device, confirmed recurring beyond the introduction: Section 2.4 ("Evidence Relationships") and Section 2.5 ("Limitation Of Training-based AI For Digital Forensics") both use the same bolded-label-plus-explanation convention documented for FairGEM's three challenges, but typeset with lowercase roman numerals -- "i) Contextual Relationships: ...", "ii) Causal Relationships: ...", up to "vi)" in 2.4, and "i) Data Scarcity: ...", "ii) Data Pre-processing Challenges: ...", "iii) AI Models Lack Adaptability: ...", "iv) Difficulty in Extracting Evidence Relationships: ..." in 2.5. This confirms the "bold label, then plain-prose explanation, never bold the whole sentence" device is a house convention across this co-author circle, used repeatedly through a paper's body, not reserved for a single introduction paragraph.
- Related work is not a separate section; it is folded into Section 3 as worked examples. The most sustained case, "3.2.5 The Local LLM-driven Framework for Digital Forensic" (on Sharma et al.'s ForensicLLM), runs a full page and disposes of the neighbor appreciatively rather than competitively: "The retrieval-enhanced fine-tuning approach proposed by Sharma et al. significantly impacts digital forensic practice by reducing common limitations associated with general-purpose language models... equipping forensic investigators with trustworthy, traceable analytical support..." -- summarize-then-praise, not summarize-then-distinguish-from-us (there is no "unlike Sharma et al., we..." sentence at all, because this is a survey rather than a competing method).
- Limitations are not a short paragraph anywhere -- they are an entire first-class section, "4 Challenges and Limitations of Leveraging LLM in Digital Forensics," with two subsections (4.1 "LLM Inherent Challenges": Hallucinations, Interpretability and Explainability, Lack of Domain-Specific Knowledge, Bias and Fairness; 4.2 "Digital Forensics-Specific Challenges": Chain of Custody and Evidentiary Integrity, Non-determinism and Reproducibility, Prompt Sensitivity, Lack of Standardization, Training and Expertise Requirements). Each bolded label is followed by a short real-world anecdote (a named or described incident) and then the generalizable lesson. This is the opposite of the Pass-2 "limitations get mined by reviewers, so minimize them" guidance recorded elsewhere in the review-lessons file -- but that guidance is explicitly about a method paper's limitations section functioning as a critique list; here, in a survey whose stated contribution is exactly a catalogue of LLM limitations in forensics, the limitations section is not incidental disclosure but the paper's second main deliverable (the first being the capabilities overview), which is a genre difference worth keeping distinct from a rule violation.
- "Future Directions" (Section 5) is likewise a full section, not a paragraph, with six subsections (5.1-5.6), each again a bolded subsection header followed by unbolded prose -- the same device at one structural level up.
- Conclusion: Section 6, one paragraph, 7 sentences (~150 words), ending on a consequence/impact sentence -- "the thoughtful integration of LLMs holds significant promise in advancing digital forensic practices, fostering trust and reliability, and contributing to more equitable and just judicial outcomes" -- not on an artefact list, matching the abstract's own closing pattern and the Pass-2 rule already on record for this co-author circle.

### ICDM 2023 exemplar, cited from the review-lessons file's own direct reading

Wang, Narasimhan, Yao, Zhang, "Mitigating Multisource Biases in Graph Neural Networks via Real Counterfactual Samples," IEEE ICDM 2023, DOI 10.1109/ICDM58522.2023.00073. Measurements recorded in the review-lessons SKILL.md (not re-read here, per this task's citation instruction extended to this paper since it was already read from source and is repeatedly cross-checked in that file, not merely assumed from genre):

- Canonical six-section shape: Introduction, Related Work, Notations and Preliminaries, Method, Experiments, Conclusion.
- Abstract: five-part order -- broad impact with no citations, gap, why the gap is serious, method at high level, experimental setting and headline result. No numbered procedure ("first we, then we") inside the abstract.
- Introduction: 4-6 paragraphs -- problem/stakes, prior work and its shortfall, a "what made it hard" challenges paragraph (the paragraph most drafts skip, per the file's own framing), the paper's approach with a "to the best of our knowledge" novelty claim, a bulleted contributions list (3-5 items, ordered by importance), and a closing roadmap paragraph ("The remainder of this paper is structured as follows: Section II provides an overview...").
- Related work: exactly two or three lettered subsections, each with a bold title, each citing three to five works on one genuinely overlapping thread (the model paper uses exactly two: "Graph Neural Networks" and "Fairness on graphs").
- Notations and Preliminaries: a short, separate section; background is folded in here rather than left standing alone in the introduction.
- Experiments: organized around research questions -- item 5b of the same file states this explicitly, that "the model paper in Pass 3... answers each research question by naming the table that addresses it and then stating the conclusion in words before moving on." This mirrors the "Targeting Negative Flips" venue-sample paper in Part 1, which is the only one of the four venue papers to frame its experiments section as numbered research questions.
- Conclusion: one paragraph, restating the contribution without introducing anything new.
- Cross-cutting house preferences recorded from Zichong Wang's own review comments on this project (not inferred from the exemplar paper, but from his direct feedback, and worth stating alongside the exemplar because they describe how he wants prose built, not just how one paper happened to be built): no bolding of a full sentence for emphasis (bold is reserved for genuine run-in headings; a single italicized sentence per paper is the ceiling for emphasis); no addressing a reviewer directly in the paper's own prose ("a reviewer might ask," "we anticipate the objection that" are rebuttal-letter language, not paper language); no narrating a cited work's review status inline; universal-negative claims ("no prior work does X") must be scoped to what was actually surveyed.

### Genre caveat

This is a survey, and several of its structural choices (no contributions list, no introduction-embedded challenges paragraph, a full-section rather than paragraph-length limitations treatment) track the survey genre rather than contradicting the method-paper conventions measured from FairGEM and ICDM 2023. Where the two genres agree -- the bolded-label-plus-plain-prose enumeration device, ending the abstract and conclusion on an idea/consequence rather than an artefact list, opening the abstract with uncited broad impact -- the agreement is more informative precisely because it survives the genre change.

---

## PART 3: SYNTHESIS

### Conventions where the venue sample and the co-authors' own work agree: follow without argument

1. **Bolded run-in label, then plain unbolded prose, never a bolded whole sentence, for enumerating sub-points.** Measured in the venue sample (BanglaDialecto's inline "(a)/(b)"; Negative Flips' "a)/b)" subsubsection headers) and in every co-author-circle paper checked (FairGEM's three "i)/ii)/(iii)" challenges; the ICDM 2023 exemplar; the Digital Forensics survey's "i)/ii)/..." labels in two different sections). Zichong Wang's own review comment (item 7d in the review-lessons file) makes this explicit and prohibits bolding a full explanatory sentence. Apply this device for both the introduction's challenges and any body-section enumeration.
2. **Single-paragraph conclusions that end on an idea or consequence, never on an artefact/deliverable list.** All four venue papers end their conclusions on a results/impact sentence rather than "we release X" (DP-TabICL is the only one that appends a further future-work sentence in the same paragraph; BanglaDialecto is the only one with a second, separate Future Works paragraph). FairGEM's contributions list closes on the outcome achieved rather than the last deliverable; the Digital Forensics survey's conclusion ends on "advancing digital forensic practices... contributing to more equitable and just judicial outcomes." The ICDM 2023 exemplar's explicit rule is "one paragraph... restating the contribution without introducing anything new."
3. **Abstracts open with broad, uncited impact and close on a finding/consequence, not a deliverable inventory.** All four venue abstracts and the Digital Forensics abstract follow this shape; the ICDM 2023 checklist states it as a five-part rule, and Pass 2 item 1 of the review-lessons file states it as a rule in its own right ("the abstract must end on the idea, not on the artefact list").
4. **A dedicated "Limitations" heading is rare to absent, and where limitations appear, they should be facts a reviewer would find unprompted, not a padded confession list.** Zero of the four venue papers carry a section literally titled "Limitations." Where a limitations-like admission appears at all in the venue sample (BanglaDialecto, Negative Flips), it is a few sentences folded into Discussion or Conclusion. This matches the review-lessons file's own Pass 2 item 7 rule almost exactly. (The one counter-instance -- the Digital Forensics survey's full-section "Challenges and Limitations" -- is explained by genre: a survey's stated contribution is partly a catalogue of limitations, which is not the situation of a method or audit paper such as this project's own manuscript.)
5. **Two-column IEEE format, roughly 8-10 pages for a regular submission.** Confirmed for three of four venue papers (the fourth, a "Short" paper, ran long on figures) and assumed throughout the ICDM 2023 checklist for "8 to 10 page submissions at ICDM, BigData and similar."
6. **When a Related Work section exists as its own heading, two lettered or bold-titled subsections, each citing multiple works on one thread, is the workable shape.** DP-TabICL's "Related Work" section uses exactly two bold run-in subsection labels ("Tabular LLMs:", "Differentially Private In-Context Learning:"), and Negative Flips' "Background and Prior Art" section uses exactly two lettered subsections ("A. Active Learning", "B. Software Regression"), each citing three or more works. This matches the ICDM 2023 checklist's explicit rule of "two or three lettered subsections, each with a bold title... three to five works per subsection" verbatim. (BanglaDialecto is the outlier, folding related work into the introduction via inline citations rather than a separate section -- worth noting as a legitimate alternative for a short paper, not a violation.)

### Where the venue sample and the co-authors' own work disagree, or the co-authors disagree with themselves: needs a decision

1. **Whether the introduction needs an explicit, bolded "challenges" paragraph tied to the paper's own specific angle.** None of the four venue-sample papers has this device inside its introduction (BanglaDialecto's inline "(a)/(b)" tags in the intro describe prior-work categories, not this paper's own difficulty; the other three venue papers have no comparable paragraph at all). By contrast, this is a named, deliberate co-author preference: Wenbin Zhang's guidance as relayed, cross-checked against FairGEM's own measured paragraph 4 and the ICDM 2023 checklist's paragraph 3 ("what made it hard... the paragraph most drafts skip"). **Decision needed:** because the venue does not enforce this and the co-authors explicitly want it, the paper should include it deliberately as a co-author-circle convention rather than a venue requirement, and should be honest in framing it that way if asked.
2. **Whether the introduction ends on a roadmap paragraph or on the contributions list.** Split within the venue sample itself: DP-TabICL and Beyond Human Vision both end with an explicit "the remainder of this work is as follows" / by-section roadmap; BanglaDialecto and Negative Flips do not, instead scattering forward section-pointers through the prose (Negative Flips) or omitting a roadmap entirely (BanglaDialecto). Split within the co-author sample too: the ICDM 2023 exemplar's checklist explicitly calls for a closing roadmap paragraph, while FairGEM's own introduction, as measured in the review-lessons file, has no separate roadmap paragraph and ends on its contributions list instead. **Decision needed:** pick one and apply it consistently; given the split is close to even on both sides, ending on the contributions list (matching FairGEM, the more recent and more directly comparable co-author paper, and two of the four venue papers) is a defensible default, with roadmap sentences folded as forward references inside earlier paragraphs (as Negative Flips does) rather than a separate paragraph.
3. **Whether the contributions list is bulleted, inline-numbered, or absent.** The venue sample shows three different typesettings and one paper with no list at all (BanglaDialecto's inline "(1)(2)(3)"; DP-TabICL's bulleted list; Negative Flips' displayed "1)/2)/3)" list; Beyond Human Vision has no contributions list whatsoever). The co-author convention, per the ICDM 2023 checklist, is specific and consistent: "contributions, as a bulleted list. Three to five items. Order them by importance, not by chronology." **Decision needed:** given the venue tolerates all four shapes but the co-authors have a stated, specific preference, default to the bulleted list ordered by importance, matching one of the four venue papers (DP-TabICL) exactly.
4. **Whether the abstract reports exact digit metrics or spells quantities out in prose.** Three of the four venue-sample abstracts (DP-TabICL, Beyond Human Vision, Negative Flips) and the co-authors' own Digital Forensics abstract contain zero digit numerals, preferring "eight real-world tabular datasets" to "8 datasets." Only BanglaDialecto reports digit metrics directly in its abstract ("CER of 0.8%," "BLEU score of 41.6%"). This project's own manuscript reports headline counts that are central to its claim (confirmed-finding counts, environment counts, escape rates against the pre-registered kill gate), so the majority convention of spelling out small counts in prose, while reporting genuine rate/percentage results as figures, is likely the right default, but this is a judgment call rather than a settled convention: no co-author paper measured here reports a comparably central quantitative headline result in its abstract, so there is no direct precedent to defer to.

### What could not be confirmed

The Intelligent Data Mining special session's own paper list for 2022-2025 could not be located within this task's search budget (see the sourcing note in Part 1); the four sampled papers are IEEE BigData 2024 main-track papers, explicitly labelled as such rather than as special-session papers. The venue conventions above should be read as "IEEE BigData 2024 main-conference practice, very likely but not confirmed to extend to the Intelligent Data Mining special session," since both tracks use the same IEEE two-column template and the same page-limit rule per the 2023 special-session call for papers.
