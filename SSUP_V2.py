def post_started(sender, analysis): # DO NOT EDIT THIS LINE
    define_dpf_workflow(analysis)

# Load properties under the python result for better user experiences
def reload_props():

    this.PropertyProvider = None

    provider = Provider()

    # =========================================================
    # SETTINGS
    # =========================================================

    settings = provider.AddGroup("Total Stress Settings")

    # Static Structural result file
    static_rst = settings.AddProperty(
        "Static RST Path",
        Control.Expression
    )
    static_rst.Value = ""

    # Harmonic frequency to evaluate
    freq = settings.AddProperty(
        "Target Frequency (Hz)",
        Control.Double
    )
    freq.Value = 120.0
    freq.ValidRange = (0.0, 1000000.0)

    # Phase sweep increment
    phase = settings.AddProperty(
        "Phase Increment (deg)",
        Control.Double
    )
    phase.Value = 5.0
    phase.ValidRange = (0.1, 180.0)

    # Warning tolerance for nearest solved frequency
    tol = settings.AddProperty(
        "Frequency Tolerance (Hz)",
        Control.Double
    )
    tol.Value = 0.5
    tol.ValidRange = (0.0, 1000000.0)

    # =========================================================
    # GEOMETRY SCOPE
    # =========================================================

    scope = provider.AddGroup("Scope")

    scope.AddProperty(
        "Geometry",
        "Scoping",
        "property_templates"
    )

    this.PropertyProvider = provider

# Main code
# Edit "RESULT_MODE" to different types of elements if applicable
#       Current supported modes: BEAM, SOLID, SHELL_BOTTOM, SHELL_TOP

def define_dpf_workflow(analysis):

    import mech_dpf
    import Ans.DataProcessing as dpf

    mech_dpf.setExtAPI(ExtAPI)

    # =========================================================
    # RESULT MODE
    #
    # Change ONLY this variable for the four Python Results:
    #
    # "SOLID"
    # "SHELL_TOP"
    # "SHELL_BOTTOM"
    # "BEAM"
    # =========================================================

    RESULT_MODE = "SOLID"


    # =========================================================
    # READ CUSTOM PROPERTIES
    # =========================================================

    static_rst = str(
        this.GetCustomPropertyByPath(
            "Total Stress Settings/Static RST Path"
        ).Value
    )

    target_frequency = float(
        this.GetCustomPropertyByPath(
            "Total Stress Settings/Target Frequency (Hz)"
        ).Value
    )

    phase_increment = float(
        this.GetCustomPropertyByPath(
            "Total Stress Settings/Phase Increment (deg)"
        ).Value
    )

    frequency_tolerance = float(
        this.GetCustomPropertyByPath(
            "Total Stress Settings/Frequency Tolerance (Hz)"
        ).Value
    )


    # =========================================================
    # CHECK INPUT
    # =========================================================

    if static_rst is None or len(static_rst.strip()) == 0:
        raise Exception(
            "Static RST Path is empty. "
            "Enter the Static Structural file.rst path."
        )

    if phase_increment <= 0.0:
        raise Exception(
            "Phase Increment must be greater than zero."
        )


    # =========================================================
    # GET GEOMETRY SCOPING
    # =========================================================

    geometry_refs = this.GetCustomPropertyByPath(
        "Scope/Geometry/Geometry Selection"
    ).Value

    element_scoping = mech_dpf.GetElementScopingByRefId(
        geometry_refs
    )

    if element_scoping is None:
        raise Exception(
            "No geometry is selected in Scope/Geometry."
        )


    # =========================================================
    # DATA SOURCES
    # =========================================================

    # Static Structural result file
    static_ds = dpf.DataSources(static_rst)

    # Current Harmonic Response result file
    harmonic_ds = dpf.DataSources(
        analysis.ResultFileName
    )


    # =========================================================
    # STATIC RESULT SET
    # Use the final static result set
    # =========================================================

    static_tf_op = (
        dpf.operators.metadata.time_freq_provider()
    )

    static_tf_op.inputs.data_sources.Connect(
        static_ds
    )

    static_tf = (
        static_tf_op.outputs.time_freq_support.GetData()
    )

    static_set_id = static_tf.NumberSets

    ExtAPI.Log.WriteMessage(
        "Static result set used: " +
        str(static_set_id)
    )


    # =========================================================
    # HARMONIC FREQUENCY LIST
    #
    # Important:
    # Cluster Results means frequencies are NOT assumed
    # to be uniformly spaced.
    # =========================================================

    harmonic_tf_op = (
        dpf.operators.metadata.time_freq_provider()
    )

    harmonic_tf_op.inputs.data_sources.Connect(
        harmonic_ds
    )

    harmonic_tf = (
        harmonic_tf_op.outputs.time_freq_support.GetData()
    )

    frequencies = list(
        harmonic_tf.TimeFreqs.Data
    )

    if len(frequencies) == 0:
        raise Exception(
            "No harmonic frequencies were found."
        )


    # =========================================================
    # FIND NEAREST ACTUALLY SOLVED FREQUENCY
    # =========================================================

    closest_index = 0
    closest_difference = abs(
        frequencies[0] - target_frequency
    )

    for i in range(1, len(frequencies)):

        difference = abs(
            frequencies[i] - target_frequency
        )

        if difference < closest_difference:
            closest_difference = difference
            closest_index = i


    harmonic_set_id = closest_index + 1

    actual_frequency = frequencies[
        closest_index
    ]


    ExtAPI.Log.WriteMessage(
        "Requested frequency: " +
        str(target_frequency) +
        " Hz"
    )

    ExtAPI.Log.WriteMessage(
        "Actual solved frequency used: " +
        str(actual_frequency) +
        " Hz"
    )

    ExtAPI.Log.WriteMessage(
        "Frequency difference: " +
        str(closest_difference) +
        " Hz"
    )


    if closest_difference > frequency_tolerance:

        ExtAPI.Log.WriteWarning(
            "Requested frequency is farther than the "
            "specified tolerance. "
            "Requested = " +
            str(target_frequency) +
            " Hz; Actual = " +
            str(actual_frequency) +
            " Hz."
        )


    # =========================================================
    # TIME SCOPINGS
    # =========================================================

    static_time_scope = dpf.Scoping()
    static_time_scope.Ids = [
        static_set_id
    ]

    harmonic_time_scope = dpf.Scoping()
    harmonic_time_scope.Ids = [
        harmonic_set_id
    ]


    # =========================================================
    # STATIC STRESS OPERATOR
    # =========================================================

    static_stress_op = (
        dpf.operators.result.stress()
    )

    static_stress_op.inputs.data_sources.Connect(
        static_ds
    )

    static_stress_op.inputs.time_scoping.Connect(
        static_time_scope
    )

    static_stress_op.inputs.mesh_scoping.Connect(
        element_scoping
    )

    static_stress_op.inputs.requested_location.Connect(
        "ElementalNodal"
    )


    # =========================================================
    # HARMONIC STRESS OPERATOR
    # =========================================================

    harmonic_stress_op = (
        dpf.operators.result.stress()
    )

    harmonic_stress_op.inputs.data_sources.Connect(
        harmonic_ds
    )

    harmonic_stress_op.inputs.time_scoping.Connect(
        harmonic_time_scope
    )

    harmonic_stress_op.inputs.mesh_scoping.Connect(
        element_scoping
    )

    harmonic_stress_op.inputs.requested_location.Connect(
        "ElementalNodal"
    )


    # =========================================================
    # ELEMENT-SPECIFIC SETTINGS
    # =========================================================

    if RESULT_MODE == "SHELL_TOP":

        static_stress_op.inputs.shell_layer.Connect(0)
        harmonic_stress_op.inputs.shell_layer.Connect(0)

        ExtAPI.Log.WriteMessage(
            "Result Mode: SHELL181 TOP"
        )


    elif RESULT_MODE == "SHELL_BOTTOM":

        static_stress_op.inputs.shell_layer.Connect(1)
        harmonic_stress_op.inputs.shell_layer.Connect(1)

        ExtAPI.Log.WriteMessage(
            "Result Mode: SHELL181 BOTTOM"
        )


    elif RESULT_MODE == "BEAM":

        static_stress_op.inputs.read_beams.Connect(True)
        harmonic_stress_op.inputs.read_beams.Connect(True)

        ExtAPI.Log.WriteMessage(
            "Result Mode: BEAM188"
        )


    elif RESULT_MODE == "SOLID":

        ExtAPI.Log.WriteMessage(
            "Result Mode: SOLID186 / SOLID187"
        )


    else:

        raise Exception(
            "Unknown RESULT_MODE: " +
            str(RESULT_MODE)
        )


    # =========================================================
    # EVALUATE STATIC STRESS
    # =========================================================

    static_fc = (
        static_stress_op.outputs.fields_container.GetData()
    )

    if static_fc.FieldCount < 1:
        raise Exception(
            "No static stress was found for the selected geometry."
        )

    static_field = static_fc[0]


    # =========================================================
    # EVALUATE HARMONIC COMPLEX STRESS
    # =========================================================

    harmonic_fc = (
        harmonic_stress_op.outputs.fields_container.GetData()
    )

    if harmonic_fc.FieldCount < 2:
        raise Exception(
            "The harmonic stress result does not contain "
            "both real and imaginary fields. "
            "Check MSUP result expansion / stress output."
        )


    # =========================================================
    # PHASE SWEEP
    #
    # harmonic stress:
    #
    # S(theta)
    # = S_real*cos(theta)
    # - S_imag*sin(theta)
    #
    # DPF sweeping_phase performs this operation.
    # =========================================================

    vm_over_phase = dpf.FieldsContainer()

    vm_over_phase.Labels = ["time"]


    phase = 0.0
    phase_index = 1

    while phase < 360.0:


        # -----------------------------------------------------
        # Dynamic stress tensor at this phase
        # -----------------------------------------------------

        sweep_op = (
            dpf.operators.math.sweeping_phase_fc()
        )

        sweep_op.inputs.fields_container.Connect(
            harmonic_fc
        )

        sweep_op.inputs.angle.Connect(
            float(phase)
        )

        sweep_op.inputs.unit_name.Connect(
            "deg"
        )

        sweep_op.inputs.abs_value.Connect(
            False
        )


        dynamic_fc = (
            sweep_op.outputs.fields_container.GetData()
        )

        dynamic_field = dynamic_fc[0]


        # -----------------------------------------------------
        # TOTAL STRESS TENSOR
        #
        # static + harmonic(theta)
        # -----------------------------------------------------

        add_op = dpf.Operator("add")

        add_op.Connect(
            0,
            static_field
        )

        add_op.Connect(
            1,
            dynamic_field
        )

        total_stress_field = (
            add_op.GetOutputAsField(0)
        )


        # -----------------------------------------------------
        # VON MISES OF TOTAL STRESS
        # -----------------------------------------------------

        vm_op = (
            dpf.operators.invariant.von_mises_eqv()
        )

        vm_op.inputs.field.Connect(
            total_stress_field
        )

        # Poisson ratio is irrelevant for stress VM,
        # but this DPF operator requires this input.
        vm_op.inputs.poisson_ratio.Connect(
            0.3
        )

        vm_field = (
            vm_op.outputs.field.GetData()
        )


        # -----------------------------------------------------
        # ADD THIS PHASE TO FIELDS CONTAINER
        # -----------------------------------------------------

        vm_over_phase.Add(
            vm_field,
            {
                "time": phase_index
            }
        )


        phase += phase_increment
        phase_index += 1


    ExtAPI.Log.WriteMessage(
        "Number of phase evaluations: " +
        str(phase_index - 1)
    )


    # =========================================================
    # MAXIMUM VON MISES OVER ALL PHASES
    # =========================================================

    max_op = (
        dpf.operators.min_max.max_over_time_by_entity()
    )

    max_op.inputs.fields_container.Connect(
        vm_over_phase
    )

    max_op.inputs.abs_value.Connect(
        False
    )

    max_fc = (
        max_op.outputs.fields_container.GetData()
    )

    max_field = max_fc[0]


    # =========================================================
    # OUTPUT CONTOUR
    # =========================================================

    workflow = dpf.Workflow()

    workflow.SetOutputContour(
        max_field
    )

    workflow.Record(
        "wf_id",
        True
    )

    this.WorkflowId = (
        workflow.GetRecordedId()
    )


    ExtAPI.Log.WriteMessage(
        "Maximum total stress contour completed at " +
        str(actual_frequency) +
        " Hz."
    )