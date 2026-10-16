def post_started(sender, analysis):  # Do not edit this line
    define_dpf_workflow(analysis)

def propManager():
        # ============================================================
    # USER SETTINGS
    # ============================================================

    # Static Structural result file
    STATIC_RST = r"C:\YOUR_PROJECT\file.rst"

    # Frequency you want to investigate [Hz]
    TARGET_FREQUENCY = 120.0

    # Phase sweep increment [deg]
    # First test: 30 deg
    # Final result: 5 or 10 deg
    PHASE_INCREMENT = 30.0

    # Warning limit for nearest available frequency [Hz]
    FREQUENCY_TOLERANCE = 0.5
    return STATIC_RST,TARGET_FREQUENCY, PHASE_INCREMENT,  FREQUENCY_TOLERANCE

def define_dpf_workflow(analysis):

    import mech_dpf
    import Ans.DataProcessing as dpf

    mech_dpf.setExtAPI(ExtAPI)

    STATIC_RST,TARGET_FREQUENCY, PHASE_INCREMENT,  FREQUENCY_TOLERANCE = propManager()

    # ------------------------------------------------------------
    # Result type
    # SOLID
    # SHELL_TOP
    # SHELL_BOTTOM
    # BEAM
    # ------------------------------------------------------------

    RESULT_MODE = "SOLID"


    # ============================================================
    # DATA SOURCES
    # ============================================================

    ExtAPI.Log.WriteMessage(
        "===== Maximum Static + Harmonic Stress ====="
    )

    ExtAPI.Log.WriteMessage(
        "Result mode = " + RESULT_MODE
    )

    static_ds = dpf.DataSources(STATIC_RST)

    harmonic_ds = dpf.DataSources(
        analysis.ResultFileName
    )


    # ============================================================
    # FIND LAST STATIC RESULT SET
    # ============================================================

    static_tf_op = dpf.operators.metadata.time_freq_provider()

    static_tf_op.inputs.data_sources.Connect(
        static_ds
    )

    static_tf = (
        static_tf_op.outputs.time_freq_support.GetData()
    )

    static_set_id = static_tf.NumberSets

    ExtAPI.Log.WriteMessage(
        "Static result set = " +
        str(static_set_id)
    )


    # ============================================================
    # GET ACTUAL HARMONIC FREQUENCIES
    # ============================================================

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
            "No harmonic frequencies found in result file."
        )


    # ============================================================
    # FIND CLOSEST SOLVED FREQUENCY
    # ============================================================

    closest_index = 0

    closest_difference = abs(
        float(frequencies[0]) -
        TARGET_FREQUENCY
    )

    for i in range(1, len(frequencies)):

        difference = abs(
            float(frequencies[i]) -
            TARGET_FREQUENCY
        )

        if difference < closest_difference:

            closest_difference = difference
            closest_index = i


    actual_frequency = float(
        frequencies[closest_index]
    )

    harmonic_set_id = closest_index + 1


    ExtAPI.Log.WriteMessage(
        "Requested frequency = " +
        str(TARGET_FREQUENCY) +
        " Hz"
    )

    ExtAPI.Log.WriteMessage(
        "Actual frequency used = " +
        str(actual_frequency) +
        " Hz"
    )

    ExtAPI.Log.WriteMessage(
        "Frequency difference = " +
        str(closest_difference) +
        " Hz"
    )

    if closest_difference > FREQUENCY_TOLERANCE:

        ExtAPI.Log.WriteWarning(
            "Nearest solved frequency is outside "
            "the requested tolerance."
        )


    # ============================================================
    # TIME SCOPINGS
    # ============================================================

    static_time_scope = dpf.Scoping()
    static_time_scope.Ids = [
        static_set_id
    ]

    harmonic_time_scope = dpf.Scoping()
    harmonic_time_scope.Ids = [
        harmonic_set_id
    ]


    # ============================================================
    # STATIC STRESS
    # ============================================================

    static_stress = (
        dpf.operators.result.stress()
    )

    static_stress.inputs.data_sources.Connect(
        static_ds
    )

    static_stress.inputs.time_scoping.Connect(
        static_time_scope
    )

    static_stress.inputs.requested_location.Connect(
        "ElementalNodal"
    )


    # ============================================================
    # HARMONIC STRESS
    # ============================================================

    harmonic_stress = (
        dpf.operators.result.stress()
    )

    harmonic_stress.inputs.data_sources.Connect(
        harmonic_ds
    )

    harmonic_stress.inputs.time_scoping.Connect(
        harmonic_time_scope
    )

    harmonic_stress.inputs.requested_location.Connect(
        "ElementalNodal"
    )


    # ============================================================
    # ELEMENT-TYPE SETTINGS
    # ============================================================

    if RESULT_MODE == "SOLID":

        # Split by element shape.
        # Solid fields will later be selected.
        static_stress.inputs.split_shells.Connect(True)
        harmonic_stress.inputs.split_shells.Connect(True)

        ExtAPI.Log.WriteMessage(
            "Processing SOLID186 / SOLID187."
        )


    elif RESULT_MODE == "SHELL_TOP":

        static_stress.inputs.split_shells.Connect(True)
        harmonic_stress.inputs.split_shells.Connect(True)

        static_stress.inputs.shell_layer.Connect(0)
        harmonic_stress.inputs.shell_layer.Connect(0)

        ExtAPI.Log.WriteMessage(
            "Processing SHELL181 TOP."
        )


    elif RESULT_MODE == "SHELL_BOTTOM":

        static_stress.inputs.split_shells.Connect(True)
        harmonic_stress.inputs.split_shells.Connect(True)

        static_stress.inputs.shell_layer.Connect(1)
        harmonic_stress.inputs.shell_layer.Connect(1)

        ExtAPI.Log.WriteMessage(
            "Processing SHELL181 BOTTOM."
        )


    elif RESULT_MODE == "BEAM":

        static_stress.inputs.read_beams.Connect(True)
        harmonic_stress.inputs.read_beams.Connect(True)

        ExtAPI.Log.WriteMessage(
            "Processing BEAM188."
        )


    else:

        raise Exception(
            "Unknown RESULT_MODE: " +
            RESULT_MODE
        )


    # ============================================================
    # EVALUATE STRESS FIELDS
    # ============================================================

    static_fc = (
        static_stress.outputs.fields_container.GetData()
    )

    harmonic_fc = (
        harmonic_stress.outputs.fields_container.GetData()
    )


    ExtAPI.Log.WriteMessage(
        "Static fields = " +
        str(static_fc.FieldCount)
    )

    ExtAPI.Log.WriteMessage(
        "Harmonic fields = " +
        str(harmonic_fc.FieldCount)
    )


    # ============================================================
    # SELECT ELEMENT SHAPE
    #
    # DPF elshape convention:
    #
    # 1 = shell
    # 2 = solid
    # 3 = beam
    # ============================================================

    if RESULT_MODE == "SOLID":
        target_elshape = 2

    elif RESULT_MODE == "SHELL_TOP":
        target_elshape = 1

    elif RESULT_MODE == "SHELL_BOTTOM":
        target_elshape = 1

    elif RESULT_MODE == "BEAM":
        target_elshape = 3


    # ============================================================
    # EXTRACT STATIC FIELD FOR TARGET ELEMENT SHAPE
    # ============================================================

    static_field = None

    for i in range(static_fc.FieldCount):

        field = static_fc[i]

        try:
            label_space = static_fc.GetLabelSpace(i)

            if label_space.ContainsKey("elshape"):

                if int(label_space["elshape"]) == target_elshape:
                    static_field = field
                    break

            else:

                # Beam-only or non-split case
                if RESULT_MODE == "BEAM":
                    static_field = field
                    break

        except:

            if RESULT_MODE == "BEAM":
                static_field = field
                break


    if static_field is None:
        raise Exception(
            "Could not find the requested static element shape."
        )


    # ============================================================
    # PHASE SWEEP
    # ============================================================

    phase_fields = dpf.FieldsContainer()

    phase_fields.Labels = ["time"]

    phase = 0.0
    phase_id = 1


    while phase < 360.0:

        ExtAPI.Log.WriteMessage(
            "Evaluating phase = " +
            str(phase) +
            " deg"
        )


        # --------------------------------------------------------
        # Convert complex harmonic stress into stress at phase
        #
        # S(theta) =
        # Real*cos(theta) - Imag*sin(theta)
        # --------------------------------------------------------

        phase_op = (
            dpf.operators.math.sweeping_phase_fc()
        )

        phase_op.inputs.fields_container.Connect(
            harmonic_fc
        )

        phase_op.inputs.angle.Connect(
            phase
        )

        phase_op.inputs.unit_name.Connect(
            "deg"
        )

        phase_op.inputs.abs_value.Connect(
            False
        )

        harmonic_phase_fc = (
            phase_op.outputs.fields_container.GetData()
        )


        # --------------------------------------------------------
        # Select target element shape from harmonic phase result
        # --------------------------------------------------------

        harmonic_phase_field = None

        for j in range(harmonic_phase_fc.FieldCount):

            field = harmonic_phase_fc[j]

            try:

                label_space = (
                    harmonic_phase_fc.GetLabelSpace(j)
                )

                if label_space.ContainsKey("elshape"):

                    if int(
                        label_space["elshape"]
                    ) == target_elshape:

                        harmonic_phase_field = field
                        break

                else:

                    if RESULT_MODE == "BEAM":
                        harmonic_phase_field = field
                        break

            except:

                if RESULT_MODE == "BEAM":
                    harmonic_phase_field = field
                    break


        if harmonic_phase_field is None:

            raise Exception(
                "Could not find harmonic field "
                "for requested element shape."
            )


        # --------------------------------------------------------
        # STATIC + HARMONIC STRESS TENSOR
        # --------------------------------------------------------

        add_op = dpf.operators.math.add()

        add_op.inputs.fieldA.Connect(
            static_field
        )

        add_op.inputs.fieldB.Connect(
            harmonic_phase_field
        )

        total_stress_field = (
            add_op.outputs.field.GetData()
        )


        # --------------------------------------------------------
        # TOTAL VON MISES
        # --------------------------------------------------------

        vm_op = (
            dpf.operators.invariant.von_mises_eqv()
        )

        vm_op.inputs.field.Connect(
            total_stress_field
        )

        vm_field = (
            vm_op.outputs.field.GetData()
        )


        # --------------------------------------------------------
        # STORE THIS PHASE
        # --------------------------------------------------------

        phase_fields.Add(
            vm_field,
            {
                "time": phase_id
            }
        )


        phase = phase + PHASE_INCREMENT
        phase_id = phase_id + 1


    # ============================================================
    # MAXIMUM OVER ALL PHASES
    # ============================================================

    max_op = (
        dpf.operators.min_max.max_over_time_by_entity()
    )

    max_op.inputs.fields_container.Connect(
        phase_fields
    )

    max_op.inputs.abs_value.Connect(
        False
    )

    max_fc = (
        max_op.outputs.fields_container.GetData()
    )

    max_field = max_fc[0]


    ExtAPI.Log.WriteMessage(
        "Phase sweep complete."
    )

    ExtAPI.Log.WriteMessage(
        "Number of evaluated phases = " +
        str(phase_id - 1)
    )


    # ============================================================
    # OUTPUT CONTOUR
    # ============================================================

    forward_op = (
        dpf.operators.utility.forward_field()
    )

    forward_op.inputs.field.Connect(
        max_field
    )

    workflow = dpf.Workflow()

    workflow.Add(
        forward_op
    )

    workflow.SetOutputContour(
        forward_op
    )

    workflow.Record(
        "wf_id",
        False
    )

    this.WorkflowId = (
        workflow.GetRecordedId()
    )


    ExtAPI.Log.WriteMessage(
        "Maximum total stress contour created."
    )