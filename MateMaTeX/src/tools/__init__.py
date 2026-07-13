"""
Tools module for MateMaTeX.
Contains custom tools for LaTeX generation, PDF compilation, etc.
"""

from .pdf_generator import (
    compile_latex_to_pdf,
    clean_ai_output,
    ensure_preamble,
    validate_latex_syntax,
    STANDARD_PREAMBLE
)

from .word_exporter import (
    latex_to_word,
    convert_latex_file_to_word,
    is_word_export_available,
)

from .section_editor import (
    parse_sections,
    get_section_summary,
    replace_section,
    extract_section,
    generate_section_prompt,
)

from .topic_suggester import (
    get_topic_suggestions,
    get_related_topics,
    get_prerequisite_topics,
)

from .print_optimizer import (
    create_print_version,
    optimize_for_ink_saving,
    add_page_breaks,
    create_answer_sheet,
    remove_solutions,
    PRINT_PREAMBLE,
)

from .batch_generator import (
    BatchJob,
    BatchResult,
    create_batch_jobs,
    run_batch,
    merge_batch_results,
    get_batch_summary,
    estimate_batch_time,
)

from .formula_library import (
    Formula,
    FORMULA_LIBRARY,
    get_all_formulas,
    get_formulas_by_category,
    get_categories,
    search_formulas,
    get_formula_latex_block,
    get_formula_for_topic,
)

from .qr_generator import (
    is_qr_available,
    generate_qr_code,
    generate_answer_qr,
    decode_answer_qr,
    extract_answers_from_latex,
    generate_qr_for_worksheet,
    get_qr_latex_code,
)

from .difficulty_analyzer import (
    ExerciseAnalysis,
    ContentAnalysis,
    analyze_exercise,
    analyze_content,
    get_difficulty_distribution_chart_data,
    get_difficulty_emoji,
    format_analysis_summary,
)

from .template_builder import (
    CustomTemplate,
    load_custom_templates,
    save_custom_templates,
    create_template,
    update_template,
    delete_template,
    get_template,
    increment_usage,
    get_popular_templates,
    get_recent_templates,
    search_templates,
    export_template,
    import_template,
    get_preset_templates,
    PRESET_TEMPLATES,
)

from .rubric_generator import (
    Rubric,
    RubricCriterion,
    generate_rubric,
    rubric_to_latex,
    rubric_to_markdown,
    get_grade_from_score,
    generate_quick_rubric,
    MATH_CRITERIA,
)

from .lk20_coverage import (
    CompetencyGoal,
    CoverageResult,
    CoverageReport,
    get_goals_for_grade,
    analyze_coverage,
    format_coverage_report,
    get_coverage_badge,
    LK20_GOALS,
)

from .differentiation import (
    DifferentiatedContent,
    DifferentiatedSet,
    LEVEL_CONFIG,
    get_level_prompt,
    adjust_content_difficulty,
    create_level_header,
    create_differentiated_set,
    get_differentiation_summary,
    merge_differentiated_pdf,
    get_level_recommendations,
)

from .favorites import (
    Favorite,
    load_favorites,
    save_favorites,
    add_favorite,
    get_favorite,
    update_favorite,
    delete_favorite,
    toggle_pin,
    get_pinned_favorites,
    get_recent_favorites,
    get_top_rated_favorites,
    get_most_used_favorites,
    search_favorites,
    get_favorites_by_grade,
    get_favorites_by_tag,
    get_all_tags,
    get_favorites_stats,
    render_star_rating,
    format_favorite_card,
)

from .exercise_bank import (
    Exercise,
    load_exercises,
    save_exercises,
    extract_exercises_from_latex,
    add_exercise,
    add_exercises_from_latex,
    get_exercise,
    delete_exercise,
    update_exercise,
    search_exercises,
    get_exercises_by_topic,
    get_exercises_by_difficulty,
    get_popular_exercises,
    get_recent_exercises,
    get_all_topics,
    get_exercise_stats,
    create_worksheet_from_exercises,
    format_exercise_preview,
)

from .keyboard_shortcuts import (
    SHORTCUTS,
    get_shortcut_js,
    get_shortcuts_help_html,
    get_shortcut_list,
)

from .pdf_preview import (
    get_pdf_base64,
    get_pdf_bytes_base64,
    create_pdf_preview_html,
    create_pdf_preview_with_controls,
    create_pdf_fallback_html,
    get_pdf_page_count,
    create_preview_thumbnail_html,
)

from .theme_manager import (
    ThemeColors,
    DARK_THEME,
    LIGHT_THEME,
    get_theme,
    generate_theme_css,
    get_theme_toggle_html,
    get_theme_switcher_styles,
)

from .organization import (
    Folder,
    Tag,
    load_folders,
    save_folders,
    create_folder,
    get_folder,
    update_folder,
    delete_folder,
    get_child_folders,
    get_folder_path,
    load_tags,
    save_tags,
    create_tag,
    get_tag,
    get_tag_by_name,
    update_tag,
    delete_tag,
    get_popular_tags,
    search_tags,
    render_folder_badge,
    render_tag_badge,
    render_tags_row,
    FOLDER_COLORS,
    FOLDER_ICONS,
    TAG_COLORS,
)

from .global_search import (
    SearchResult,
    global_search,
    search_favorites,
    search_exercises,
    search_history,
    search_templates,
    get_type_icon,
    get_type_label,
    render_search_result_html,
    get_search_suggestions,
)

from .geogebra import (
    GeoGebraGraph,
    GRAPH_TEMPLATES,
    get_geogebra_embed_html,
    get_geogebra_link,
    create_graph_from_template,
    parse_function_from_latex,
    extract_functions_from_content,
    get_graph_latex_code,
    get_template_list,
    render_template_selector_html,
    GEOGEBRA_COMMAND_REFERENCE,
)

from .content_index import (
    load_content_index,
    save_content_index,
    get_item_folder,
    set_item_folder,
    remove_item_from_index,
    get_folder_counts,
    filter_by_folder,
)

from .usage_dashboard import (
    UsageStats,
    record_generation,
    get_usage_stats,
    get_dashboard_html,
    get_activity_chart_data,
    get_achievements,
    render_achievements_html,
)

from .pptx_exporter import (
    is_pptx_available,
    SlideContent,
    parse_latex_to_slides,
    create_pptx,
    latex_to_pptx,
    get_pptx_preview,
)

from .watermark import (
    WatermarkConfig,
    add_watermark_to_latex,
    create_header_footer_latex,
    get_logo_latex,
    SCHOOL_TEMPLATES,
    apply_template as apply_watermark_template,
    render_watermark_preview_html,
)

from .graph_templates import (
    GraphTemplate,
    ALL_TEMPLATES as ALL_GRAPH_TEMPLATES,
    TEMPLATES_BY_CATEGORY as GRAPH_TEMPLATES_BY_CATEGORY,
    TEMPLATES_BY_GRADE as GRAPH_TEMPLATES_BY_GRADE,
    get_templates_for_grade,
    get_templates_for_category,
    get_template_by_id,
    get_all_categories as get_graph_categories,
    get_template_summary_for_prompt,
)

from .cover_page import (
    CoverPageConfig,
    COVER_STYLES,
    generate_cover_page_latex,
    insert_cover_page,
    get_cover_style_options,
)

__all__ = [
    # PDF tools
    "compile_latex_to_pdf",
    "clean_ai_output",
    "ensure_preamble",
    "validate_latex_syntax",
    "STANDARD_PREAMBLE",
    # Word tools
    "latex_to_word",
    "convert_latex_file_to_word",
    "is_word_export_available",
    # Section editor
    "parse_sections",
    "get_section_summary",
    "replace_section",
    "extract_section",
    "generate_section_prompt",
    # Topic suggester
    "get_topic_suggestions",
    "get_related_topics",
    "get_prerequisite_topics",
    # Print optimizer
    "create_print_version",
    "optimize_for_ink_saving",
    "add_page_breaks",
    "create_answer_sheet",
    "remove_solutions",
    "PRINT_PREAMBLE",
    # Batch generator
    "BatchJob",
    "BatchResult",
    "create_batch_jobs",
    "run_batch",
    "merge_batch_results",
    "get_batch_summary",
    "estimate_batch_time",
    # Formula library
    "Formula",
    "FORMULA_LIBRARY",
    "get_all_formulas",
    "get_formulas_by_category",
    "get_categories",
    "search_formulas",
    "get_formula_latex_block",
    "get_formula_for_topic",
    # QR generator
    "is_qr_available",
    "generate_qr_code",
    "generate_answer_qr",
    "decode_answer_qr",
    "extract_answers_from_latex",
    "generate_qr_for_worksheet",
    "get_qr_latex_code",
    # Difficulty analyzer
    "ExerciseAnalysis",
    "ContentAnalysis",
    "analyze_exercise",
    "analyze_content",
    "get_difficulty_distribution_chart_data",
    "get_difficulty_emoji",
    "format_analysis_summary",
    # Template builder
    "CustomTemplate",
    "load_custom_templates",
    "save_custom_templates",
    "create_template",
    "update_template",
    "delete_template",
    "get_template",
    "increment_usage",
    "get_popular_templates",
    "get_recent_templates",
    "search_templates",
    "export_template",
    "import_template",
    "get_preset_templates",
    "PRESET_TEMPLATES",
    # Rubric generator
    "Rubric",
    "RubricCriterion",
    "generate_rubric",
    "rubric_to_latex",
    "rubric_to_markdown",
    "get_grade_from_score",
    "generate_quick_rubric",
    "MATH_CRITERIA",
    # LK20 coverage
    "CompetencyGoal",
    "CoverageResult",
    "CoverageReport",
    "get_goals_for_grade",
    "analyze_coverage",
    "format_coverage_report",
    "get_coverage_badge",
    "LK20_GOALS",
    # Differentiation
    "DifferentiatedContent",
    "DifferentiatedSet",
    "LEVEL_CONFIG",
    "get_level_prompt",
    "adjust_content_difficulty",
    "create_level_header",
    "create_differentiated_set",
    "get_differentiation_summary",
    "merge_differentiated_pdf",
    "get_level_recommendations",
    # Favorites
    "Favorite",
    "load_favorites",
    "save_favorites",
    "add_favorite",
    "get_favorite",
    "update_favorite",
    "delete_favorite",
    "toggle_pin",
    "get_pinned_favorites",
    "get_recent_favorites",
    "get_top_rated_favorites",
    "get_most_used_favorites",
    "search_favorites",
    "get_favorites_by_grade",
    "get_favorites_by_tag",
    "get_all_tags",
    "get_favorites_stats",
    "render_star_rating",
    "format_favorite_card",
    # Exercise bank
    "Exercise",
    "load_exercises",
    "save_exercises",
    "extract_exercises_from_latex",
    "add_exercise",
    "add_exercises_from_latex",
    "get_exercise",
    "delete_exercise",
    "update_exercise",
    "search_exercises",
    "get_exercises_by_topic",
    "get_exercises_by_difficulty",
    "get_popular_exercises",
    "get_recent_exercises",
    "get_all_topics",
    "get_exercise_stats",
    "create_worksheet_from_exercises",
    "format_exercise_preview",
    # Keyboard shortcuts
    "SHORTCUTS",
    "get_shortcut_js",
    "get_shortcuts_help_html",
    "get_shortcut_list",
    # PDF preview
    "get_pdf_base64",
    "get_pdf_bytes_base64",
    "create_pdf_preview_html",
    "create_pdf_preview_with_controls",
    "create_pdf_fallback_html",
    "get_pdf_page_count",
    "create_preview_thumbnail_html",
    # Theme manager
    "ThemeColors",
    "DARK_THEME",
    "LIGHT_THEME",
    "get_theme",
    "generate_theme_css",
    "get_theme_toggle_html",
    "get_theme_switcher_styles",
    # Organization (folders & tags)
    "Folder",
    "Tag",
    "load_folders",
    "save_folders",
    "create_folder",
    "get_folder",
    "update_folder",
    "delete_folder",
    "get_child_folders",
    "get_folder_path",
    "load_tags",
    "save_tags",
    "create_tag",
    "get_tag",
    "get_tag_by_name",
    "update_tag",
    "delete_tag",
    "get_popular_tags",
    "search_tags",
    "render_folder_badge",
    "render_tag_badge",
    "render_tags_row",
    "FOLDER_COLORS",
    "FOLDER_ICONS",
    "TAG_COLORS",
    # Global search
    "SearchResult",
    "global_search",
    "search_favorites",
    "search_exercises",
    "search_history",
    "search_templates",
    "get_type_icon",
    "get_type_label",
    "render_search_result_html",
    "get_search_suggestions",
    # GeoGebra integration
    "GeoGebraGraph",
    "GRAPH_TEMPLATES",
    "get_geogebra_embed_html",
    "get_geogebra_link",
    "create_graph_from_template",
    "parse_function_from_latex",
    "extract_functions_from_content",
    "get_graph_latex_code",
    "get_template_list",
    "render_template_selector_html",
    "GEOGEBRA_COMMAND_REFERENCE",
    # Content index (folders mapping)
    "load_content_index",
    "save_content_index",
    "get_item_folder",
    "set_item_folder",
    "remove_item_from_index",
    "get_folder_counts",
    "filter_by_folder",
    # Usage dashboard
    "UsageStats",
    "record_generation",
    "get_usage_stats",
    "get_dashboard_html",
    "get_activity_chart_data",
    "get_achievements",
    "render_achievements_html",
    # PowerPoint export
    "is_pptx_available",
    "SlideContent",
    "parse_latex_to_slides",
    "create_pptx",
    "latex_to_pptx",
    "get_pptx_preview",
    # Watermark
    "WatermarkConfig",
    "add_watermark_to_latex",
    "create_header_footer_latex",
    "get_logo_latex",
    "SCHOOL_TEMPLATES",
    "apply_watermark_template",
    "render_watermark_preview_html",
    # Graph templates
    "GraphTemplate",
    "ALL_GRAPH_TEMPLATES",
    "GRAPH_TEMPLATES_BY_CATEGORY",
    "GRAPH_TEMPLATES_BY_GRADE",
    "get_templates_for_grade",
    "get_templates_for_category",
    "get_template_by_id",
    "get_graph_categories",
    "get_template_summary_for_prompt",
    # Cover page
    "CoverPageConfig",
    "COVER_STYLES",
    "generate_cover_page_latex",
    "insert_cover_page",
    "get_cover_style_options",
]
