//! ---
//! displayName: customer CIM build plan
//! category: Parser
//! description: Import a build plan produced by converters/cim_to_inspire/build_plan.py into the Migration Model
//! sourceFormat: AEM Forms XDP (via CIM build plan JSON)
//! ---
//
// STATUS: DRAFT, NOT EXECUTED.  This script has never been run against the
// migration-stack because Gradle/Maven Central and Inspire Designer are not
// reachable from the environment it was written in.  Treat every builder call
// as a hypothesis until a Quadient practitioner runs it (see gate G5).
//
// Usage (from a migration-examples checkout, after copying this file next to
// the other parsers): set BUILD_PLAN to the path of <form>.plan.json.
package com.quadient.migration.example.customer

import com.quadient.migration.api.Migration
import com.quadient.migration.api.dto.migrationmodel.PageOptions
import com.quadient.migration.api.dto.migrationmodel.builder.DocumentObjectBuilder
import com.quadient.migration.api.dto.migrationmodel.builder.ParagraphStyleBuilder
import com.quadient.migration.api.dto.migrationmodel.builder.TextStyleBuilder
import com.quadient.migration.api.dto.migrationmodel.builder.VariableBuilder
import com.quadient.migration.shared.Alignment
import com.quadient.migration.shared.DataType
import com.quadient.migration.shared.DocumentObjectType
import com.quadient.migration.shared.Size
import groovy.json.JsonSlurper

import static com.quadient.migration.example.common.util.InitMigration.initMigration

Migration migration = initMigration(this.binding)

def planPath = System.getenv("BUILD_PLAN")
assert planPath : "BUILD_PLAN env var must point to a <form>.plan.json"
def plan = new JsonSlurper().parse(new File(planPath))
assert plan.plan_version == "1.0" : "unsupported plan_version ${plan.plan_version}"

for (v in plan.variables) {
    migration.variableRepository.upsert(
        new VariableBuilder(v.id)
            .name(v.name)
            .dataType(DataType.valueOf(v.data_type))
            .originLocations(v.source_soms)
            .addCustomField("resolution", v.resolution)
            .build())
}

for (s in plan.text_styles) {
    migration.textStyleRepository.upsert(
        new TextStyleBuilder(s.id).definition {
            it.fontFamily(s.font_family)
            it.size(Size.ofPoints(s.size_pt as double))
            it.bold(s.bold)
            it.italic(s.italic)
            it.underline(s.underline)
        }.build())
}

for (p in plan.paragraph_styles) {
    migration.paragraphStyleRepository.upsert(
        new ParagraphStyleBuilder(p.id).definition {
            it.alignment(Alignment.valueOf(p.alignment))
        }.build())
}

// Children first so every documentObjectRef points at an upserted object.
def blocksById = plan.blocks.collectEntries { [(it.id): it] }
def emitted = [] as Set
def emitBlock
emitBlock = { block ->
    if (emitted.contains(block.id)) return
    for (childId in block.child_block_ids) emitBlock(blocksById[childId])
    def builder = new DocumentObjectBuilder(block.id, DocumentObjectType.Block)
        .name(block.name)
        .internal(true)
        .addCustomField("cim_container", block.container_id)
        .addCustomField("role", block.role)
    for (para in block.paragraphs) {
        builder.paragraph {
            it.styleRef("${para.style_id}_para")
            if (para.kind == "text") {
                it.text { t -> t.styleRef(para.style_id); t.string(para.text) }
            } else if (para.kind == "variable") {
                it.text { t ->
                    t.styleRef(para.style_id)
                    if (para.caption) t.string(para.caption + " ")
                    t.variableRef(para.variable_id)
                }
            } else {
                throw new IllegalStateException("unknown paragraph kind ${para.kind}")
            }
        }
    }
    for (childId in block.child_block_ids) builder.documentObjectRef(childId)
    migration.documentObjectRepository.upsert(builder.build())
    emitted.add(block.id)
}
for (block in plan.blocks) emitBlock(block)

for (page in plan.pages) {
    def builder = new DocumentObjectBuilder(page.id, DocumentObjectType.Page)
        .internal(true)
        .options(new PageOptions(Size.ofMillimeters(page.width_mm as double), Size.ofMillimeters(page.height_mm as double)))
    for (area in page.areas) {
        builder.area {
            it.position { pos ->
                pos.left(Size.ofMillimeters(area.left_mm as double))
                pos.top(Size.ofMillimeters(area.top_mm as double))
                pos.width(Size.ofMillimeters(area.width_mm as double))
                pos.height(Size.ofMillimeters(area.height_mm as double))
            }
            it.flowToNextPage(area.flow_to_next_page)
            it.documentObjectRef(area.block_id)
        }
    }
    migration.documentObjectRepository.upsert(builder.build())
}

def template = new DocumentObjectBuilder(plan.template.id, DocumentObjectType.Template)
    .name(plan.form_code)
    .addCustomField("source_sha256", plan.source_sha256)
    .addCustomField("skipped_nodes", plan.skipped.size().toString())
    .addCustomField("decisions_required", plan.decisions_required.size().toString())
for (pageId in plan.template.page_ids) template.documentObjectRef(pageId)
migration.documentObjectRepository.upsert(template.build())

println "upserted ${plan.variables.size()} variables, ${plan.blocks.size()} blocks, ${plan.pages.size()} pages for ${plan.form_code}"
println "skipped ${plan.skipped.size()} nodes; ${plan.decisions_required.size()} human decisions outstanding"
